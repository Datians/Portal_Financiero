from flask import Flask, render_template, session

from .config import Config
from .extensions import db, bcrypt, mail, migrate


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializar extensiones
    db.init_app(app)
    # Estas extensiones no cambian la lógica del portal, pero evitan
    # errores en tiempo de ejecución cuando se usan (registro, hashing, etc.).
    bcrypt.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # ===== RUTA PÚBLICA PRINCIPAL (LANDING) =====
    @app.route("/")
    def landing():
        return render_template("landing.html")

    # ===== CONTEXT PROCESSOR: current_user / is_authenticated =====
    @app.context_processor
    def inject_user():
        from .models import User  # import aquí para evitar ciclos

        user = None
        if "user_id" in session:
            user = User.query.get(session["user_id"])
        return {
            "current_user": user,
            "is_authenticated": user is not None,
        }

    # ===== REGISTRO DE BLUEPRINTS =====
    from .auth.routes import auth_bp
    from .finance.routes import finance_bp
    from .mfa.routes import mfa_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(finance_bp, url_prefix="/finance")
    app.register_blueprint(mfa_bp, url_prefix="/mfa")

    return app
