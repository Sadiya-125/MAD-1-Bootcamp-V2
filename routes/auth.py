from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from helpers import (
    EMAIL_RE,
    MIN_PASSWORD_LENGTH,
    SIGNUP_ROLES,
    USERNAME_RE,
    is_safe_next,
    is_web_url,
    login_required,
)
from models import User, db

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
    if g.user.is_student:
        return redirect(url_for("student.dashboard"))
    if g.user.is_instructor:
        return redirect(url_for("instructor.dashboard"))
    return redirect(url_for("admin.dashboard"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = g.user
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        bio = request.form.get("bio", "").strip()
        avatar = request.form.get("avatar", "").strip()

        errors = []
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        elif email != user.email and db.session.scalar(
            db.select(User).where(User.email == email)
        ):
            errors.append("Another account already uses that email.")
        if len(bio) > 1000:
            errors.append("Bio must be 1000 characters or fewer.")
        if avatar and not is_web_url(avatar):
            errors.append("Avatar must be a link starting with http:// or https://.")

        if errors:
            for message in errors:
                flash(message, "error")
        else:
            user.email, user.bio, user.avatar = email, bio, avatar or None
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("auth.profile"))
    return render_template("profile.html", user=user)


@bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if not g.user.check_password(current):
        flash("Your current password is incorrect.", "error")
    elif len(new) < MIN_PASSWORD_LENGTH:
        flash(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
    elif new != confirm:
        flash("New passwords do not match.", "error")
    else:
        g.user.set_password(new)
        db.session.commit()
        flash("Password changed.", "success")
    return redirect(url_for("auth.profile"))