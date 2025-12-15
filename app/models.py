from datetime import datetime
from .extensions import db

class User(db.Model):
    """
    Usuario del portal.

    Se usa tanto para el flujo de registro / login / MFA como para
    la relación con las cuentas financieras simuladas.
    """
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User {self.email}>"

class OtpCode(db.Model):
    """
    Código OTP de un solo uso para el segundo factor de autenticación.

    - code: código numérico de 6 dígitos.
    - created_at: fecha de creación.
    - used: indica si ya fue utilizado.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used = db.Column(db.Boolean, default=False)

    user = db.relationship("User", backref="otp_codes")

class Account(db.Model):
    """
    Cuenta financiera simulada (Nequi, Bancolombia, Daviplata, Nu, etc.).

    - bank_type: tipo/banco (NEQUI, BANCOLOMBIA, DAVIPLATA, NU, OTRO).
    - name: alias visible para el usuario (ej. "Nequi día a día").
    - balance: saldo actual simulado.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    bank_type = db.Column(db.String(50), nullable=False, default="OTRO")
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Numeric(14, 2), default=0)

    user = db.relationship("User", backref="accounts")

class Transaction(db.Model):
    """
    Movimiento asociado a una cuenta.

    - type: 'INGRESO', 'EGRESO', 'TRANSFER_IN', 'TRANSFER_OUT', etc.
    - counterparty_account_id: para enlazar con otra cuenta en transferencias internas.
    - counterparty_email: para transferencias entre usuarios (correo del otro usuario).
    """
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255))
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    type = db.Column(db.String(20), nullable=False)

    counterparty_account_id = db.Column(db.Integer, nullable=True)
    counterparty_email = db.Column(db.String(255), nullable=True)

    account = db.relationship("Account", backref="transactions")
