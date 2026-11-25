from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from helpers import get_enrollment
from models import CATEGORIES, LEVELS, Course, db

bp = Blueprint("courses", __name__)


@bp.route("/")
def home():
    return redirect(url_for("courses.course_list"))


@bp.route("/courses")
def course_list():
    filters = {
        "q": request.args.get("q", "").strip(),
        "category": request.args.get("category", ""),
        "level": request.args.get("level", ""),
        "price": request.args.get("price", ""),
    }

    query = db.select(Course).where(Course.is_published.is_(True))
    if filters["q"]:
        like = f"%{filters['q']}%"
        query = query.where(
            Course.title.ilike(like)
            | Course.short_description.ilike(like)
            | Course.description.ilike(like)
        )
    if filters["category"] in CATEGORIES:
        query = query.where(Course.category == filters["category"])
    if filters["level"] in LEVELS:
        query = query.where(Course.level == filters["level"])
    if filters["price"] == "free":
        query = query.where(Course.price == 0)
    elif filters["price"] == "paid":
        query = query.where(Course.price > 0)
    query = query.order_by(Course.is_featured.desc(), Course.created_at.desc())

    page = db.paginate(query, per_page=9, error_out=False)
    return render_template(
        "course_list.html",
        page=page,
        filters=filters,
        categories=CATEGORIES,
        levels=LEVELS,
    )


@bp.route("/courses/<slug>")
def course_detail(slug):
    course = db.first_or_404(db.select(Course).where(Course.slug == slug))

    if not course.is_published:
        can_preview = g.user and (
            g.user.is_admin or g.user.id == course.instructor_id
        )
        if not can_preview:
            abort(404)

    enrollment = None
    if g.user and g.user.is_student:
        enrollment = get_enrollment(g.user.id, course.id)
    return render_template(
        "course_detail.html", course=course, enrollment=enrollment
    )


@bp.route("/search")
def search():
    return redirect(url_for("courses.course_list", **request.args))
