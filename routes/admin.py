from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from helpers import admin_required
from models import ROLES, Course, Enrollment, User, db

bp = Blueprint("admin", __name__)


def count(query):
    return db.session.scalar(query) or 0


@bp.route("/admin")
@admin_required
def dashboard():
    total_enrollments = count(db.select(db.func.count(Enrollment.id)))
    completed = count(
        db.select(db.func.count(Enrollment.id)).where(
            Enrollment.completed_at.is_not(None)
        )
    )
    stats = {
        "users": count(db.select(db.func.count(User.id))),
        "students": count(db.select(db.func.count(User.id)).where(User.role == "student")),
        "instructors": count(db.select(db.func.count(User.id)).where(User.role == "instructor")),
        "courses": count(db.select(db.func.count(Course.id))),
        "published": count(db.select(db.func.count(Course.id)).where(Course.is_published.is_(True))),
        "enrollments": total_enrollments,
        "completed": completed,
        "completion_rate": round(completed / total_enrollments * 100) if total_enrollments else 0,
    }

    top_courses = db.session.execute(
        db.select(Course.title, db.func.count(Enrollment.id).label("students"))
        .join(Enrollment, Enrollment.course_id == Course.id)
        .group_by(Course.id)
        .order_by(db.desc("students"))
        .limit(5)
    ).all()

    recent = db.session.scalars(
        db.select(Enrollment).order_by(Enrollment.enrolled_at.desc()).limit(8)
    ).all()
    return render_template(
        "admin_dashboard.html", stats=stats, top_courses=top_courses, recent=recent
    )


@bp.route("/admin/users")
@admin_required
def users():
    page = db.paginate(
        db.select(User).order_by(User.created_at.desc()), per_page=20, error_out=False
    )
    return render_template("admin_users.html", page=page, roles=ROLES)


@bp.route("/admin/user/<int:user_id>/role", methods=["POST"])
@admin_required
def toggle_user_role(user_id):
    user = db.get_or_404(User, user_id)
    role = request.form.get("role")
    if user.id == g.user.id:
        flash("You can't change your own role.", "error")
    elif role not in ROLES:
        flash("Unknown role.", "error")
    else:
        user.role = role
        db.session.commit()
        flash(f"{user.username} is now {'an' if role in ('admin', 'instructor') else 'a'} {role}.", "success")
    return redirect(url_for("admin.users", page=request.form.get("page", 1, type=int)))


@bp.route("/admin/user/<int:user_id>/active", methods=["POST"])
@admin_required
def toggle_user_active(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == g.user.id:
        flash("You can't deactivate your own account.", "error")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        state = "reactivated" if user.is_active else "deactivated"
        flash(f"{user.username} has been {state}.", "info")
    return redirect(url_for("admin.users", page=request.form.get("page", 1, type=int)))


@bp.route("/admin/courses")
@admin_required
def courses():
    courses = db.session.scalars(
        db.select(Course).order_by(Course.created_at.desc())
    ).all()
    return render_template("admin_courses.html", courses=courses)


@bp.route("/admin/course/<int:course_id>/feature", methods=["POST"])
@admin_required
def toggle_featured(course_id):
    course = db.get_or_404(Course, course_id)
    course.is_featured = not course.is_featured
    db.session.commit()
    flash(f"{course.title} {'is now featured' if course.is_featured else 'is no longer featured'}.", "info")
    return redirect(url_for("admin.courses"))


@bp.route("/admin/course/<int:course_id>/publish", methods=["POST"])
@admin_required
def toggle_publish(course_id):
    course = db.get_or_404(Course, course_id)
    course.is_published = not course.is_published
    db.session.commit()
    flash(f"{course.title} is now {'published' if course.is_published else 'a draft'}.", "info")
    return redirect(url_for("admin.courses"))