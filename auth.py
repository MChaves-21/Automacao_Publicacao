"""auth.py — Autenticação multi-usuário com 2FA opcional."""
from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from config import config

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Faça login para acessar o painel."

auth_bp = Blueprint("auth", __name__)

@login_manager.user_loader
def load_user(user_id: str):
    from core.models import User
    return db_get_user(int(user_id))

def db_get_user(uid: int):
    from core.models import User
    return User.query.get(uid)

def seed_admin() -> None:
    from core.models import User, UserRole, db
    if User.query.count() > 0: return
    if not config.admin_username or not config.admin_password: return
    admin = User(username=config.admin_username,
                 email=config.admin_email or f"{config.admin_username}@localhost",
                 role=UserRole.ADMIN)
    admin.set_password(config.admin_password)
    db.session.add(admin); db.session.commit()
    print(f"✅ Admin '{config.admin_username}' criado.")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("views.index"))
    error = None
    if request.method == "POST":
        from core.models import User
        ident    = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=ident).first() or User.query.filter_by(email=ident).first()
        if user and user.is_active and user.check_password(password):
            if user.otp_enabled:
                session["pre_2fa_user_id"] = user.id
                return redirect(url_for("auth.verify_2fa_login"))
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("views.index"))
        error = "Usuário ou senha incorretos."
    return render_template("login.html", error=error)

@auth_bp.route("/verify-2fa", methods=["GET", "POST"])
def verify_2fa_login():
    uid = session.get("pre_2fa_user_id")
    if not uid: return redirect(url_for("auth.login"))
    error = None
    if request.method == "POST":
        import pyotp
        user  = db_get_user(uid)
        token = request.form.get("token", "").strip()
        if user and user.otp_secret and pyotp.TOTP(user.otp_secret).verify(token):
            session.pop("pre_2fa_user_id", None)
            login_user(user, remember=True)
            return redirect(url_for("views.index"))
        error = "Código inválido. Tente novamente."
    return render_template("verify_2fa.html", error=error)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated: return redirect(url_for("views.index"))
    if request.method == "POST":
        from core.models import User, db
        username  = request.form.get("username", "").strip()
        email     = request.form.get("email", "").strip().lower()
        password  = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        errors = []
        if not username or not email or not password: errors.append("Preencha todos os campos.")
        elif len(username) < 3: errors.append("Usuário precisa ter 3+ caracteres.")
        elif len(password) < 6: errors.append("Senha precisa ter 6+ caracteres.")
        elif password != password2: errors.append("As senhas não coincidem.")
        elif User.query.filter_by(username=username).first(): errors.append("Usuário já em uso.")
        elif User.query.filter_by(email=email).first(): errors.append("E-mail já cadastrado.")
        if errors: return render_template("register.html", error=errors[0])
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user); db.session.commit()
        login_user(user, remember=True)
        return redirect(url_for("views.index"))
    return render_template("register.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
