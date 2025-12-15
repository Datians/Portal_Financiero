from decimal import Decimal
from datetime import datetime, timedelta

from flask import (
    render_template,
    session,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)

from . import finance_bp
from ..models import User, Account, Transaction, OtpCode
from ..extensions import db
from ..email_utils import send_operation_otp_email

BANK_TYPES = ["NEQUI", "BANCOLOMBIA", "DAVIPLATA", "NU", "OTRO"]

# Session keys para el flujo de OTP por operación sensible
_PENDING_OP_KEY = "pending_operation"
_PENDING_OP_OTP_ID_KEY = "pending_operation_otp_id"

def login_required(view):
    """
    Decorador muy simple que reutiliza la sesión creada por el flujo MFA.
    No toca nada del diseño de autenticación: solo verifica que exista user_id.
    """
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash("Debes iniciar sesión y completar el MFA.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper


def _generate_otp_code() -> str:
    """Genera un código OTP de 6 dígitos."""
    import random

    return f"{random.randint(0, 999999):06d}"


def _clear_pending_operation():
    session.pop(_PENDING_OP_KEY, None)
    session.pop(_PENDING_OP_OTP_ID_KEY, None)


def _start_operation_otp(user: User, op_name: str, payload: dict, title: str, detail: str = ""):
    """
    Inicia una operación sensible solicitando un OTP por correo.

    - Guarda en sesión el payload (pequeño) para continuar tras verificar el OTP.
    - Guarda el id del OTP para validar exactamente ese código (evita aceptar OTPs antiguos).
    """
    code = _generate_otp_code()
    otp = OtpCode(user_id=user.id, code=code)
    db.session.add(otp)
    db.session.commit()  # asegura otp.id

    session[_PENDING_OP_KEY] = {
        "name": op_name,
        "payload": payload,
        "title": title,
        "detail": detail,
        "created_at": datetime.utcnow().isoformat(),
    }
    session[_PENDING_OP_OTP_ID_KEY] = otp.id

    send_operation_otp_email(user, code, operation_title=title, operation_detail=detail)


def _execute_create_account(user: User, bank_type: str, name: str, initial_balance_raw: str):
    """Ejecuta la creación de cuenta con la misma lógica original."""
    if bank_type not in BANK_TYPES:
        flash("Tipo de banco no válido.", "error")
        return redirect(url_for("finance.dashboard"))

    if not name:
        flash("El nombre o alias de la cuenta es obligatorio.", "error")
        return redirect(url_for("finance.dashboard"))

    try:
        initial_balance = Decimal((initial_balance_raw or "0").strip() or "0")
    except Exception:
        flash("El saldo inicial no es válido.", "error")
        return redirect(url_for("finance.dashboard"))

    acc = Account(
        user_id=user.id,
        bank_type=bank_type,
        name=name,
        balance=initial_balance,
    )
    db.session.add(acc)
    db.session.flush()  # para obtener acc.id

    if initial_balance != 0:
        tx = Transaction(
            account_id=acc.id,
            amount=initial_balance,
            type="INGRESO",
            description="Saldo inicial",
        )
        db.session.add(tx)

    db.session.commit()
    flash("Cuenta creada correctamente.", "success")
    return redirect(url_for("finance.dashboard"))


def _execute_transfer_internal(user: User, from_id: str, to_id: str, amount_raw: str, description: str):
    """Ejecuta la transferencia interna con la misma lógica original."""
    if from_id == to_id:
        flash("Debes seleccionar cuentas distintas para transferir.", "error")
        return redirect(url_for("finance.dashboard"))

    try:
        amount = Decimal((amount_raw or "").strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        flash("El monto de la transferencia no es válido.", "error")
        return redirect(url_for("finance.dashboard"))

    from_acc = Account.query.filter_by(id=from_id, user_id=user.id).first()
    to_acc = Account.query.filter_by(id=to_id, user_id=user.id).first()

    if not from_acc or not to_acc:
        flash("No se encontraron las cuentas seleccionadas.", "error")
        return redirect(url_for("finance.dashboard"))

    if from_acc.balance < amount:
        flash("Saldo insuficiente en la cuenta de origen.", "error")
        return redirect(url_for("finance.dashboard"))

    from_acc.balance -= amount
    to_acc.balance += amount

    tx_out = Transaction(
        account_id=from_acc.id,
        amount=-amount,
        type="TRANSFER_OUT",
        description=description,
        counterparty_account_id=to_acc.id,
    )
    tx_in = Transaction(
        account_id=to_acc.id,
        amount=amount,
        type="TRANSFER_IN",
        description=description,
        counterparty_account_id=from_acc.id,
    )

    db.session.add_all([tx_out, tx_in])
    db.session.commit()

    flash("Transferencia interna realizada correctamente.", "success")
    return redirect(url_for("finance.dashboard"))


def _execute_transfer_external(user: User, from_id: str, recipient_email: str, amount_raw: str, description: str):
    """Ejecuta la transferencia a otro usuario con la misma lógica original."""
    if not recipient_email:
        flash("Debes indicar el correo del destinatario.", "error")
        return redirect(url_for("finance.dashboard"))

    try:
        amount = Decimal((amount_raw or "").strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        flash("El monto de la transferencia no es válido.", "error")
        return redirect(url_for("finance.dashboard"))

    from_acc = Account.query.filter_by(id=from_id, user_id=user.id).first()
    if not from_acc:
        flash("La cuenta de origen no existe o no te pertenece.", "error")
        return redirect(url_for("finance.dashboard"))

    if from_acc.balance < amount:
        flash("Saldo insuficiente en la cuenta de origen.", "error")
        return redirect(url_for("finance.dashboard"))

    recipient = User.query.filter_by(email=recipient_email).first()
    if not recipient:
        flash("No se encontró un usuario con ese correo.", "error")
        return redirect(url_for("finance.dashboard"))

    to_acc = Account.query.filter_by(user_id=recipient.id).first()
    if not to_acc:
        flash("El usuario destino no tiene cuentas registradas.", "error")
        return redirect(url_for("finance.dashboard"))

    # Ajuste de saldos
    from_acc.balance -= amount
    to_acc.balance += amount

    tx_out = Transaction(
        account_id=from_acc.id,
        amount=-amount,
        type="TRANSFER_OUT",
        description=description,
        counterparty_account_id=to_acc.id,
        counterparty_email=recipient.email,
    )
    tx_in = Transaction(
        account_id=to_acc.id,
        amount=amount,
        type="TRANSFER_IN",
        description=description,
        counterparty_account_id=from_acc.id,
        counterparty_email=user.email,
    )

    db.session.add_all([tx_out, tx_in])
    db.session.commit()

    flash("Transferencia enviada correctamente al usuario destino.", "success")
    return redirect(url_for("finance.dashboard"))


@finance_bp.route("/confirmar-operacion", methods=["GET", "POST"])
@login_required
def confirmar_operacion():
    """Pantalla de verificación OTP previa a ejecutar una operación sensible."""
    op = session.get(_PENDING_OP_KEY)
    otp_id = session.get(_PENDING_OP_OTP_ID_KEY)

    if not op or not otp_id:
        flash("No hay ninguna operación pendiente por confirmar.", "info")
        return redirect(url_for("finance.gestion"))

    user = User.query.get_or_404(session.get("user_id"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not code:
            flash("Debes ingresar el código OTP.", "error")
            return redirect(url_for("finance.confirmar_operacion"))

        otp = OtpCode.query.filter_by(id=otp_id, user_id=user.id).first()
        if not otp or otp.used:
            flash("El código OTP ya fue utilizado o no es válido.", "error")
            _clear_pending_operation()
            return redirect(url_for("finance.gestion"))

        if otp.code != code:
            flash("Código OTP inválido.", "error")
            return redirect(url_for("finance.confirmar_operacion"))

        max_age = current_app.config.get("OTP_EXP_MINUTES", 5)
        if otp.created_at < datetime.utcnow() - timedelta(minutes=max_age):
            flash("El código OTP ha expirado. Reenvíalo para continuar.", "error")
            return redirect(url_for("finance.confirmar_operacion"))

        # Marcar OTP como usado
        otp.used = True
        db.session.commit()

        # Limpiar sesión de operación pendiente (evita re-ejecución por refresh)
        payload = op.get("payload", {})
        op_name = op.get("name")
        _clear_pending_operation()

        # Ejecutar operación con la misma lógica de siempre
        if op_name == "create_account":
            return _execute_create_account(
                user,
                payload.get("bank_type", "OTRO"),
                (payload.get("name") or "").strip(),
                payload.get("initial_balance", "0"),
            )

        if op_name == "transfer_internal":
            return _execute_transfer_internal(
                user,
                payload.get("from_account_id"),
                payload.get("to_account_id"),
                payload.get("amount", ""),
                (payload.get("description") or "").strip() or "Transferencia interna",
            )

        if op_name == "transfer_external":
            return _execute_transfer_external(
                user,
                payload.get("from_account_id"),
                (payload.get("recipient_email") or "").lower().strip(),
                payload.get("amount", ""),
                (payload.get("description") or "").strip() or "Transferencia a otro usuario",
            )

        flash("Operación pendiente desconocida. Vuelve a intentarlo.", "error")
        return redirect(url_for("finance.gestion"))

    # En GET: construir un resumen más amable para la vista
    summary = {
        "title": op.get("title", "Confirmar operación"),
        "detail": op.get("detail", ""),
        "name": op.get("name", ""),
    }
    return render_template("finance/confirmar_operacion.html", user=user, op=op, summary=summary)


@finance_bp.route("/confirmar-operacion/cancelar", methods=["POST"])
@login_required
def cancelar_operacion():
    _clear_pending_operation()
    flash("Operación cancelada.", "info")
    return redirect(url_for("finance.gestion"))


@finance_bp.route("/confirmar-operacion/reenviar", methods=["POST"])
@login_required
def reenviar_otp_operacion():
    op = session.get(_PENDING_OP_KEY)
    if not op:
        flash("No hay ninguna operación pendiente para reenviar OTP.", "info")
        return redirect(url_for("finance.gestion"))

    user = User.query.get_or_404(session.get("user_id"))
    # Generar nuevo OTP y actualizar el otp_id en sesión
    code = _generate_otp_code()
    otp = OtpCode(user_id=user.id, code=code)
    db.session.add(otp)
    db.session.commit()
    session[_PENDING_OP_OTP_ID_KEY] = otp.id

    send_operation_otp_email(user, code, operation_title=op.get("title", "Confirmación de operación"), operation_detail=op.get("detail", ""))
    flash("Te reenviamos un nuevo código OTP a tu correo.", "info")
    return redirect(url_for("finance.confirmar_operacion"))

@finance_bp.route("/dashboard")
@login_required
def dashboard():
    user = User.query.get(session["user_id"])
    accounts = Account.query.filter_by(user_id=user.id).all()
    total_balance = sum(a.balance for a in accounts) if accounts else 0
    return render_template(
        "finance/dashboard.html",
        user=user,
        accounts=accounts,
        total_balance=total_balance,
    )

@finance_bp.route("/gestion")
@login_required
def gestion():
    user = User.query.get(session["user_id"])
    accounts = Account.query.filter_by(user_id=user.id).all()
    total_balance = sum(a.balance for a in accounts) if accounts else 0
    return render_template(
        "finance/gestion.html",
        user=user,
        accounts=accounts,
        total_balance=total_balance,
        bank_types=BANK_TYPES,
    )

@finance_bp.route("/accounts/create", methods=["POST"])
@login_required
def create_account():
    """
    Crea una cuenta bancaria simulada asociada al usuario.
    Solo afecta a la capa interna de datos; el MFA permanece igual.
    """
    user_id = session.get("user_id")
    user = User.query.get_or_404(user_id)

    bank_type = request.form.get("bank_type", "OTRO")
    name = request.form.get("name", "").strip()
    initial_balance_raw = request.form.get("initial_balance", "0").strip() or "0"

    if bank_type not in BANK_TYPES:
        flash("Tipo de banco no válido.", "error")
        return redirect(url_for("finance.dashboard"))

    if not name:
        flash("El nombre o alias de la cuenta es obligatorio.", "error")
        return redirect(url_for("finance.dashboard"))

    try:
        initial_balance = Decimal(initial_balance_raw)
    except Exception:
        flash("El saldo inicial no es válido.", "error")
        return redirect(url_for("finance.dashboard"))

    # OTP por operación sensible: no ejecutamos la creación aún.
    detail = f"Banco: {bank_type} · Alias: {name} · Saldo inicial: ${initial_balance:,.2f}"
    _start_operation_otp(
        user,
        op_name="create_account",
        payload={
            "bank_type": bank_type,
            "name": name,
            "initial_balance": initial_balance_raw,
        },
        title="Creación de cuenta bancaria",
        detail=detail,
    )
    flash("Te enviamos un código OTP para confirmar la creación de la cuenta.", "info")
    return redirect(url_for("finance.confirmar_operacion"))

@finance_bp.route("/transfer/internal", methods=["POST"])
@login_required
def transfer_internal():
    """
    Transferencia entre cuentas del mismo usuario.
    Actualiza saldos y crea transacciones de salida y entrada.
    """
    user_id = session.get("user_id")
    user = User.query.get_or_404(user_id)

    from_id = request.form.get("from_account_id")
    to_id = request.form.get("to_account_id")
    amount_raw = request.form.get("amount", "").strip()
    description = request.form.get("description", "").strip() or "Transferencia interna"

    if from_id == to_id:
        flash("Debes seleccionar cuentas distintas para transferir.", "error")
        return redirect(url_for("finance.dashboard"))

    try:
        amount = Decimal(amount_raw)
        if amount <= 0:
            raise ValueError
    except Exception:
        flash("El monto de la transferencia no es válido.", "error")
        return redirect(url_for("finance.dashboard"))

    from_acc = Account.query.filter_by(id=from_id, user_id=user.id).first()
    to_acc = Account.query.filter_by(id=to_id, user_id=user.id).first()

    if not from_acc or not to_acc:
        flash("No se encontraron las cuentas seleccionadas.", "error")
        return redirect(url_for("finance.dashboard"))

    if from_acc.balance < amount:
        flash("Saldo insuficiente en la cuenta de origen.", "error")
        return redirect(url_for("finance.dashboard"))

    # OTP por operación sensible
    detail = (
        f"De: {from_acc.bank_type} · {from_acc.name} → "
        f"A: {to_acc.bank_type} · {to_acc.name} · "
        f"Monto: ${amount:,.2f}"
    )
    _start_operation_otp(
        user,
        op_name="transfer_internal",
        payload={
            "from_account_id": from_id,
            "to_account_id": to_id,
            "amount": amount_raw,
            "description": description,
        },
        title="Transferencia interna",
        detail=detail,
    )
    flash("Te enviamos un código OTP para confirmar la transferencia interna.", "info")
    return redirect(url_for("finance.confirmar_operacion"))

@finance_bp.route("/transfer/external", methods=["POST"])
@login_required
def transfer_external():
    """
    Transferencia a otro usuario identificado por correo electrónico.
    Utiliza la primera cuenta del usuario destino como cuenta receptora.
    """
    user_id = session.get("user_id")
    sender = User.query.get_or_404(user_id)

    from_id = request.form.get("from_account_id")
    recipient_email = request.form.get("recipient_email", "").lower().strip()
    amount_raw = request.form.get("amount", "").strip()
    description = request.form.get("description", "").strip() or "Transferencia a otro usuario"

    if not recipient_email:
        flash("Debes indicar el correo del destinatario.", "error")
        return redirect(url_for("finance.dashboard"))

    try:
        amount = Decimal(amount_raw)
        if amount <= 0:
            raise ValueError
    except Exception:
        flash("El monto de la transferencia no es válido.", "error")
        return redirect(url_for("finance.dashboard"))

    from_acc = Account.query.filter_by(id=from_id, user_id=sender.id).first()
    if not from_acc:
        flash("La cuenta de origen no existe o no te pertenece.", "error")
        return redirect(url_for("finance.dashboard"))

    if from_acc.balance < amount:
        flash("Saldo insuficiente en la cuenta de origen.", "error")
        return redirect(url_for("finance.dashboard"))

    recipient = User.query.filter_by(email=recipient_email).first()
    if not recipient:
        flash("No se encontró un usuario con ese correo.", "error")
        return redirect(url_for("finance.dashboard"))

    # Para simplificar: se usa la primera cuenta del usuario destino.
    to_acc = Account.query.filter_by(user_id=recipient.id).first()
    if not to_acc:
        flash("El usuario destino no tiene cuentas registradas.", "error")
        return redirect(url_for("finance.dashboard"))

    # OTP por operación sensible
    detail = (
        f"Desde: {from_acc.bank_type} · {from_acc.name} → "
        f"Destino: {recipient.email} · "
        f"Monto: ${amount:,.2f}"
    )
    _start_operation_otp(
        sender,
        op_name="transfer_external",
        payload={
            "from_account_id": from_id,
            "recipient_email": recipient_email,
            "amount": amount_raw,
            "description": description,
        },
        title="Transferencia a otro usuario",
        detail=detail,
    )
    flash("Te enviamos un código OTP para confirmar la transferencia.", "info")
    return redirect(url_for("finance.confirmar_operacion"))

@finance_bp.route("/movimientos/<int:account_id>")
@login_required
def movimientos(account_id):
    """
    Vista de movimientos de una cuenta concreta.
    """
    user_id = session.get("user_id")
    user = User.query.get_or_404(user_id)
    account = Account.query.filter_by(id=account_id, user_id=user.id).first_or_404()
    txs = (
        Transaction.query.filter_by(account_id=account.id)
        .order_by(Transaction.date.desc())
        .all()
    )
    return render_template(
        "finance/movimientos.html", user=user, account=account, txs=txs
    )
