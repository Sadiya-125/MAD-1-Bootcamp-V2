from functools import wraps

import click
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, abort

from config import Config
from models import db, User


# ---------- Access decorators ----------

def login_required(view):
    """Send the user to the login page if nobody is logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Allow only users whose role is in `roles`. Others get a 403 page."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ---------- App factory ----------

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Runs before every request: look up the logged-in user from the session.
    @app.before_request
    def load_user():
        user_id = session.get("user_id")
        g.user = db.session.get(User, user_id) if user_id else None
        if g.user is not None and not g.user.is_active:
            session.clear()
            g.user = None

    # ---------- Public pages ----------

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")
            role = request.form.get("role", "student")

            error = None
            if not username or not email or not password:
                error = "All fields are required."
            elif len(password) < 8:
                error = "Password must be at least 8 characters."
            elif password != confirm:
                error = "Passwords don't match."
            elif role not in ("student", "instructor"):  # nobody can sign up as admin
                error = "Pick a valid role."
            elif User.query.filter_by(username=username).first():
                error = "That username is taken."
            elif User.query.filter_by(email=email).first():
                error = "That email is already registered."

            if error:
                flash(error, "error")
                return render_template("register.html", form=request.form)

            user = User(username=username, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created. You can log in now.", "success")
            return redirect(url_for("login"))

        return render_template("register.html", form={})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()

            if user is None or not user.check_password(password):
                flash("Wrong username or password.", "error")
                return render_template("login.html", username=username)
            if not user.is_active:
                flash("This account has been deactivated.", "error")
                return render_template("login.html", username=username)

            session.clear()
            session["user_id"] = user.id
            flash(f"Welcome back, {user.username}!", "success")

            # Only follow `next` if it's a path on our own site.
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))

        return render_template("login.html", username="")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You've been logged out.", "success")
        return redirect(url_for("home"))

    # ---------- Dashboards ----------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        # One link for everyone; it sends each role to its own page.
        return redirect(url_for(f"{g.user.role}_dashboard"))

    @app.route("/student")
    @role_required("student")
    def student_dashboard():
        return render_template("dashboard.html", title="Student dashboard")

    @app.route("/instructor")
    @role_required("instructor")
    def instructor_dashboard():
        return render_template("dashboard.html", title="Instructor dashboard")

    @app.route("/admin")
    @role_required("admin")
    def admin_dashboard():
        users = User.query.order_by(User.id).all()
        return render_template("dashboard.html", title="Admin dashboard", users=users)

    # ---------- Errors ----------

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    # ---------- CLI ----------

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(username, email, password):
        """Create an admin user from the terminal."""
        if User.query.filter((User.username == username) | (User.email == email)).first():
            click.echo("A user with that username or email already exists.")
            return
        admin = User(username=username, email=email.lower(), role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin '{username}' created.")

    # Makes `db` and `User` available in `flask shell` without importing.
    @app.shell_context_processor
    def shell_context():
        return {"db": db, "User": User}

    return app
