from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from helpers import (
    EMAIL_RE,
    MIN_PASSWORD_LENGTH,
    SIGNUP_ROLES,
    USERNAME_RE,
    is_safe_next,
    login_required,
)
from models import Course, Enrollment, User, db

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("auth.dashboard"))

    form = {"username": "", "email": "", "role": "student"}
    if request.method == "POST":
        form["username"] = request.form.get("username", "").strip()
        form["email"] = request.form.get("email", "").strip().lower()
        form["role"] = request.form.get("role", "student")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not USERNAME_RE.match(form["username"]):
            errors.append(
                "Username must be 3 to 30 characters: letters, numbers or underscores."
            )
        if not EMAIL_RE.match(form["email"]):
            errors.append("Enter a valid email address.")
        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
        if password != confirm:
            errors.append("Passwords do not match.")
        if form["role"] not in SIGNUP_ROLES:
            errors.append("Choose either Student or Instructor.")

        if not errors:
            if db.session.scalar(
                db.select(User).where(User.username == form["username"])
            ):
                errors.append("That username is already taken.")
            if db.session.scalar(
                db.select(User).where(User.email == form["email"])
            ):
                errors.append("An account with that email already exists.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("register.html", form=form), 400

        user = User(
            username=form["username"], email=form["email"], role=form["role"]
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created. You can log in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("auth.dashboard"))

    identifier = ""
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        user = db.session.scalar(
            db.select(User).where(
                (User.username == identifier)
                | (User.email == identifier.lower())
            )
        )

        if user is None or not user.check_password(password):
            flash("Incorrect username/email or password.", "error")
            return render_template("login.html", identifier=identifier), 401
        if not user.is_active:
            flash("This account has been deactivated.", "error")
            return render_template("login.html", identifier=identifier), 403

        session.clear()
        session["user_id"] = user.id
        flash(f"Welcome back, {user.username}!", "success")

        next_url = request.args.get("next")
        if is_safe_next(next_url):
            return redirect(next_url)
        return redirect(url_for("auth.dashboard"))

    return render_template("login.html", identifier=identifier)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    user = g.user
    if user.is_student:
        return redirect(url_for("student.dashboard"))
    if user.is_instructor:
        return redirect(url_for("instructor.dashboard"))
    stats = {}
    if user.is_student:
        stats["enrolled"] = len(user.enrollments)
        stats["completed"] = sum(1 for e in user.enrollments if e.completed_at)
    elif user.is_instructor:
        stats["courses"] = len(user.taught_courses)
        stats["published"] = sum(1 for c in user.taught_courses if c.is_published)
        stats["students"] = sum(len(c.enrollments) for c in user.taught_courses)
    elif user.is_admin:
        stats["users"] = db.session.scalar(db.select(db.func.count(User.id)))
        stats["courses"] = db.session.scalar(db.select(db.func.count(Course.id)))
        stats["enrollments"] = db.session.scalar(
            db.select(db.func.count(Enrollment.id))
        )
    return render_template("dashboard.html", stats=stats)
