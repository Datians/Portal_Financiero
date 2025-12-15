from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)

from ..extensions import db
from ..models import User, Account, Transaction, OtpCode
from ..security import hash_password, check_password
from ..email_utils import (
    send_verification_email,
    confirm_email_token,
    send_otp_email,
)
from . import auth_bp


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Si ya hay sesión activa, no tiene sentido registrar de nuevo
    if session.get("user_id"):
        return redirect(url_for("finance.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Correo y contraseña son obligatorios.", "error")
            return redirect(url_for("auth.register"))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Este correo ya está registrado.", "error")
            return redirect(url_for("auth.register"))

        # Crear usuario
        user = User(email=email, password_hash=hash_password(password))
        db.session.add(user)
        db.session.commit()

        # Crear cuenta financiera de ejemplo
        acc = Account(
            user_id=user.id,
            name="Cuenta Ahorros Principal",
            balance=1_500_000,
        )
        db.session.add(acc)
        db.session.commit()

        # Transacción de depósito inicial
        tx1 = Transaction(
            account_id=acc.id,
            description="Depósito inicial",
            amount=1_500_000,
            type="ingreso",
        )
        db.session.add(tx1)
        db.session.commit()

        # Enviar correo de verificación (Resend)
        send_verification_email(user)
        return render_template(
            "auth/email_verification_sent.html",
            email=email,
        )

    return render_template("auth/register.html")


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    try:
        email = confirm_email_token(token)
    except Exception:
        flash("El enlace de verificación es inválido o ha expirado.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first_or_404()
    if not user.email_verified:
        user.email_verified = True
        db.session.commit()

    return render_template("auth/email_verified_ok.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Si ya hay sesión activa, enviamos directo al dashboard
    if session.get("user_id"):
        return redirect(url_for("finance.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not check_password(password, user.password_hash):
            flash("Credenciales inválidas.", "error")
            return redirect(url_for("auth.login"))

        if not user.email_verified:
            flash("Debes verificar tu correo antes de iniciar sesión.", "error")
            return redirect(url_for("auth.login"))

        # Generar OTP de 6 dígitos
        import random

        code = f"{random.randint(0, 999999):06d}"

        otp = OtpCode(user_id=user.id, code=code)
        db.session.add(otp)
        db.session.commit()

        # Enviar OTP al correo del usuario
        send_otp_email(user, code)

        # Guardar usuario pendiente de verificar OTP
        session["pending_otp_user_id"] = user.id
        flash("Te enviamos un código OTP a tu correo.", "info")
        return redirect(url_for("mfa.verify_otp"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    # Después de cerrar sesión, lo mandamos al inicio público
    return redirect(url_for("landing"))
