import re
from functools import wraps
from urllib.parse import urlsplit

from flask import abort, flash, g, redirect, request, url_for

from models import Enrollment, db

SIGNUP_ROLES = ("student", "instructor")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


student_required = role_required("student")
instructor_required = role_required("instructor")
admin_required = role_required("admin")


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def get_enrollment(student_id, course_id):
    return db.session.scalar(
        db.select(Enrollment).where(
            Enrollment.student_id == student_id, Enrollment.course_id == course_id
        )
    )


def is_web_url(value):
    return value.startswith(("http://", "https://"))


def is_safe_next(target):
    if not target:
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc and target.startswith("/")
