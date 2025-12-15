from flask import render_template, request, redirect, url_for, flash, session, current_app
from datetime import datetime, timedelta
from ..extensions import db
from ..models import User, OtpCode
from . import mfa_bp

@mfa_bp.route("/verify", methods=["GET", "POST"])
def verify_otp():
    user_id = session.get("pending_otp_user_id")
    if not user_id:
        flash("Inicia sesión primero.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not code:
            flash("Debes ingresar el código OTP.", "error")
            return redirect(url_for("mfa.verify_otp"))

        otp = (
            OtpCode.query.filter_by(user_id=user.id, code=code, used=False)
            .order_by(OtpCode.created_at.desc())
            .first()
        )

        if not otp:
            flash("Código OTP inválido.", "error")
            return redirect(url_for("mfa.verify_otp"))

        max_age = current_app.config.get("OTP_EXP_MINUTES", 5)
        if otp.created_at < datetime.utcnow() - timedelta(minutes=max_age):
            flash("El código OTP ha expirado.", "error")
            return redirect(url_for("mfa.verify_otp"))

        otp.used = True
        db.session.commit()

        session.pop("pending_otp_user_id", None)
        session["user_id"] = user.id
        flash("Autenticación MFA completada.", "success")
        return redirect(url_for("finance.dashboard"))

    return render_template("mfa/verify_otp.html", user=user)
