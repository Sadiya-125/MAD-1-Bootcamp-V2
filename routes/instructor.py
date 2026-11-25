from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from helpers import instructor_required, is_safe_next, is_web_url, slugify
from models import CATEGORIES, LEVELS, Course, Lesson, db

bp = Blueprint("instructor", __name__)


def unique_slug(title):
    base = slugify(title) or "course"
    slug, n = base, 2
    while db.session.scalar(db.select(Course.id).where(Course.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def read_course_form(form):
    values = {
        "title": form.get("title", "").strip(),
        "short_description": form.get("short_description", "").strip(),
        "description": form.get("description", "").strip(),
        "category": form.get("category", ""),
        "level": form.get("level", ""),
        "price": form.get("price", "0").strip() or "0",
        "thumbnail": form.get("thumbnail", "").strip(),
    }
    errors = []
    if not values["title"]:
        errors.append("Title is required.")
    elif len(values["title"]) > 200:
        errors.append("Title must be 200 characters or fewer.")
    if len(values["short_description"]) > 500:
        errors.append("Short description must be 500 characters or fewer.")
    if values["category"] not in CATEGORIES:
        errors.append("Pick a category.")
    if values["level"] not in LEVELS:
        errors.append("Pick a level.")
    try:
        values["price"] = float(values["price"])
        if values["price"] < 0:
            raise ValueError
    except ValueError:
        errors.append("Price must be a number, 0 or more.")
    if values["thumbnail"] and not is_web_url(values["thumbnail"]):
        errors.append("Thumbnail must be a link starting with http:// or https://.")
    return values, errors


def read_lesson_form(form):
    values = {
        "title": form.get("title", "").strip(),
        "content": form.get("content", "").strip(),
        "video_url": form.get("video_url", "").strip(),
        "duration": form.get("duration", "").strip(),
        "order": form.get("order", "").strip(),
        "is_free_preview": form.get("is_free_preview") == "on",
    }
    errors = []
    if not values["title"]:
        errors.append("Lesson title is required.")
    elif len(values["title"]) > 200:
        errors.append("Lesson title must be 200 characters or fewer.")
    if values["video_url"] and not is_web_url(values["video_url"]):
        errors.append("Video link must start with http:// or https://.")
    for field, label in (("duration", "Duration"), ("order", "Position")):
        if values[field] == "":
            values[field] = None
            continue
        try:
            values[field] = int(values[field])
            if values[field] < 0:
                raise ValueError
        except ValueError:
            errors.append(f"{label} must be a whole number, 0 or more.")
    return values, errors


def get_own_course(course_id):
    if course_id is None:
        abort(404)
    course = db.get_or_404(Course, course_id)
    if course.instructor_id != g.user.id:
        abort(403)
    return course


@bp.route("/instructor/dashboard")
@instructor_required
def dashboard():
    courses = sorted(g.user.taught_courses, key=lambda c: c.created_at, reverse=True)
    return render_template("instructor_dashboard.html", courses=courses)


@bp.route("/instructor/course/new", methods=["GET", "POST"])
@instructor_required
def course_create():
    values = {"price": 0}
    if request.method == "POST":
        values, errors = read_course_form(request.form)
        if not errors:
            course = Course(slug=unique_slug(values["title"]), instructor=g.user, **values)
            db.session.add(course)
            db.session.commit()
            flash("Course saved as a draft. Now add some lessons.", "success")
            return redirect(url_for("instructor.lesson_list", course_id=course.id))
        for message in errors:
            flash(message, "error")
    return render_template(
        "course_builder.html", course=None, values=values,
        categories=CATEGORIES, levels=LEVELS,
    )


@bp.route("/instructor/course/<int:course_id>/edit", methods=["GET", "POST"])
@instructor_required
def course_edit(course_id):
    course = get_own_course(course_id)
    values = {
        "title": course.title,
        "short_description": course.short_description or "",
        "description": course.description or "",
        "category": course.category,
        "level": course.level,
        "price": course.price,
        "thumbnail": course.thumbnail or "",
    }
    if request.method == "POST":
        values, errors = read_course_form(request.form)
        if not errors:
            for field, value in values.items():
                setattr(course, field, value)
            db.session.commit()
            flash("Course details updated.", "success")
            return redirect(url_for("instructor.lesson_list", course_id=course.id))
        for message in errors:
            flash(message, "error")
    return render_template(
        "course_builder.html", course=course, values=values,
        categories=CATEGORIES, levels=LEVELS,
    )


@bp.route("/instructor/course/<int:course_id>/lessons")
@instructor_required
def lesson_list(course_id):
    course = get_own_course(course_id)
    return render_template("lesson_manager.html", course=course)


@bp.route("/instructor/course/<int:course_id>/publish", methods=["POST"])
@instructor_required
def toggle_publish(course_id):
    course = get_own_course(course_id)
    if not course.is_published and not course.lessons:
        flash("Add at least one lesson before publishing.", "error")
    else:
        course.is_published = not course.is_published
        db.session.commit()
        if course.is_published:
            flash(f"{course.title} is live in the catalog.", "success")
        else:
            flash(f"{course.title} is now a draft.", "info")

    next_url = request.form.get("next")
    if is_safe_next(next_url):
        return redirect(next_url)
    return redirect(url_for("instructor.lesson_list", course_id=course.id))


@bp.route("/instructor/lesson/new", methods=["GET", "POST"])
@instructor_required
def lesson_create():
    course = get_own_course(request.args.get("course_id", type=int))
    values = {"order": len(course.lessons) + 1}
    if request.method == "POST":
        values, errors = read_lesson_form(request.form)
        if not errors:
            if values["order"] is None:
                values["order"] = len(course.lessons) + 1
            db.session.add(Lesson(course=course, **values))
            db.session.commit()
            flash("Lesson added.", "success")
            return redirect(url_for("instructor.lesson_list", course_id=course.id))
        for message in errors:
            flash(message, "error")
    return render_template("lesson_form.html", course=course, lesson=None, values=values)


@bp.route("/instructor/lesson/<int:lesson_id>/edit", methods=["GET", "POST"])
@instructor_required
def lesson_edit(lesson_id):
    lesson = db.get_or_404(Lesson, lesson_id)
    course = get_own_course(lesson.course_id)
    values = {
        "title": lesson.title,
        "content": lesson.content or "",
        "video_url": lesson.video_url or "",
        "duration": lesson.duration,
        "order": lesson.order,
        "is_free_preview": lesson.is_free_preview,
    }
    if request.method == "POST":
        values, errors = read_lesson_form(request.form)
        if not errors:
            if values["order"] is None:
                values["order"] = lesson.order
            for field, value in values.items():
                setattr(lesson, field, value)
            db.session.commit()
            flash("Lesson updated.", "success")
            return redirect(url_for("instructor.lesson_list", course_id=course.id))
        for message in errors:
            flash(message, "error")
    return render_template("lesson_form.html", course=course, lesson=lesson, values=values)


@bp.route("/instructor/lesson/<int:lesson_id>/delete", methods=["POST"])
@instructor_required
def lesson_delete(lesson_id):
    lesson = db.get_or_404(Lesson, lesson_id)
    course = get_own_course(lesson.course_id)
    db.session.delete(lesson)
    db.session.commit()
    flash(f"Deleted lesson: {lesson.title}", "info")
    return redirect(url_for("instructor.lesson_list", course_id=course.id))
