import os

import resend
from flask import current_app, url_for
from itsdangerous import URLSafeTimedSerializer


def _serializer():
    """
    Serializador que se usa para generar y validar el token
    de verificación de correo.
    """
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_email_token(email: str) -> str:
    """
    Genera un token firmado a partir del correo del usuario.
    Se usa en el enlace de verificación.
    """
    return _serializer().dumps(email, salt="email-confirm")


def confirm_email_token(token, max_age=3600):
    """
    Valida el token de verificación y devuelve el email original.
    max_age está en segundos (por defecto 1 hora).
    """
    return _serializer().loads(token, salt="email-confirm", max_age=max_age)


def _send_resend_email(to_email: str, subject: str, html_body: str):
    """
    Función interna para enviar correo usando la API HTTP de Resend.

    - Usa RESEND_API_KEY y RESEND_FROM desde el .env.
    - No lanza errores a la vista; si algo falla, lo imprime en consola.
    """
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("[Resend] ❌ Falta RESEND_API_KEY en el .env")
        return

    resend.api_key = api_key

    from_email = os.getenv(
        "RESEND_FROM",
        "Portal Financiero <onboarding@resend.dev>",
    )

    try:
        resend.Emails.send(
            {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            }
        )
        print(f"[Resend] ✅ Email enviado a {to_email}")
    except Exception as e:
        print(f"[Resend] ❌ Error enviando email a {to_email}: {e}")


def send_verification_email(user):
    """
    Envía el correo de verificación de cuenta al usuario.

    Mantiene la misma firma que la versión anterior
    para no tocar nada en auth/routes.py.
    """
    token = generate_email_token(user.email)
    verify_url = url_for("auth.verify_email", token=token, _external=True)

    html_body = f"""
        <p>Hola,</p>
        <p>Gracias por registrarte en el <strong>Portal Financiero</strong>.</p>
        <p>Para activar tu cuenta, haz clic en el siguiente enlace:</p>
        <p>
            <a href="{verify_url}"
               style="display:inline-block;padding:10px 16px;
                      background:#2563eb;color:#ffffff;
                      text-decoration:none;border-radius:6px;">
               Verificar mi correo
            </a>
        </p>
        <p>Si no puedes hacer clic, copia y pega este enlace en tu navegador:</p>
        <p>{verify_url}</p>
        <p>Si no fuiste tú quien creó la cuenta, puedes ignorar este mensaje.</p>
    """

    _send_resend_email(
        to_email=user.email,
        subject="Verifica tu correo - Portal Financiero",
        html_body=html_body,
    )


def send_otp_email(user, code: str):
    """
    Envía el código OTP de segundo factor al usuario.

    También mantiene la misma firma para no tocar mfa/routes.py.
    """
    minutes = current_app.config.get("OTP_EXP_MINUTES", 5)

    html_body = f"""
        <p>Hola,</p>
        <p>Tu código de un solo uso (OTP) para acceder al portal es:</p>
        <h2 style="letter-spacing:0.15em;">{code}</h2>
        <p>El código expira en {minutes} minutos.</p>
        <p>No compartas este código con nadie.</p>
    """

    _send_resend_email(
        to_email=user.email,
        subject="Tu código OTP de acceso - Portal Financiero",
        html_body=html_body,
    )


def send_operation_otp_email(user, code: str, operation_title: str, operation_detail: str = ""):
    """
    Envía un OTP para confirmar una operación sensible (transferencias / creación de cuentas).

    - No reemplaza el OTP de login: es un segundo OTP específico por operación.
    - Se mantiene separado para no alterar el flujo existente de /mfa/verify.
    """
    minutes = current_app.config.get("OTP_EXP_MINUTES", 5)
    detail_html = f"<p style=\"margin:0.25rem 0 0; color:#374151;\">{operation_detail}</p>" if operation_detail else ""

    html_body = f"""
        <p>Hola,</p>
        <p>Para confirmar la siguiente operación en tu <strong>Portal Financiero</strong>:</p>
        <p style="margin:0.25rem 0 0;"><strong>{operation_title}</strong></p>
        {detail_html}
        <p style="margin-top:1rem;">Tu código OTP de confirmación es:</p>
        <h2 style="letter-spacing:0.15em;">{code}</h2>
        <p>El código expira en {minutes} minutos.</p>
        <p>No compartas este código con nadie.</p>
    """

    _send_resend_email(
        to_email=user.email,
        subject="Código OTP para confirmar operación - Portal Financiero",
        html_body=html_body,
    )
