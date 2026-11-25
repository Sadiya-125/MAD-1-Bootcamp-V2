from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from helpers import get_enrollment, student_required
from models import Course, Enrollment, Lesson, LessonCompletion, db, utc_now

bp = Blueprint("student", __name__)


@bp.route("/enroll/<int:course_id>", methods=["POST"])
@student_required
def enroll(course_id):
    course = db.get_or_404(Course, course_id)
    if not course.is_published:
        abort(404)

    if get_enrollment(g.user.id, course.id):
        flash("You're already enrolled in this course.", "info")
    else:
        db.session.add(Enrollment(student=g.user, course=course))
        db.session.commit()
        flash(f"You're enrolled in {course.title}. Happy learning!", "success")
    return redirect(url_for("student.course_player", slug=course.slug))


@bp.route("/student/dashboard")
@student_required
def dashboard():
    enrollments = sorted(
        g.user.enrollments, key=lambda e: e.enrolled_at, reverse=True
    )
    return render_template("student_dashboard.html", enrollments=enrollments)


@bp.route("/learn/<slug>")
@student_required
def course_player(slug):
    course = db.first_or_404(db.select(Course).where(Course.slug == slug))
    enrollment = get_enrollment(g.user.id, course.id)
    if enrollment is None:
        flash("Enroll in this course to start learning.", "warning")
        return redirect(url_for("courses.course_detail", slug=course.slug))

    lessons = course.lessons
    done_ids = set(
        db.session.scalars(
            db.select(LessonCompletion.lesson_id)
            .join(Lesson)
            .where(
                LessonCompletion.student_id == g.user.id,
                Lesson.course_id == course.id,
            )
        )
    )

    current = None
    wanted = request.args.get("lesson", type=int)
    if wanted:
        current = next((l for l in lessons if l.id == wanted), None)
    if current is None and lessons:
        current = next((l for l in lessons if l.id not in done_ids), lessons[0])

    prev_lesson = next_lesson = None
    if current:
        i = lessons.index(current)
        prev_lesson = lessons[i - 1] if i > 0 else None
        next_lesson = lessons[i + 1] if i + 1 < len(lessons) else None

    return render_template(
        "course_player.html",
        course=course,
        enrollment=enrollment,
        lesson=current,
        done_ids=done_ids,
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
    )


@bp.route("/lesson/<int:lesson_id>/complete", methods=["POST"])
@student_required
def toggle_completion(lesson_id):
    lesson = db.get_or_404(Lesson, lesson_id)
    course = lesson.course
    enrollment = get_enrollment(g.user.id, course.id)
    if enrollment is None:
        abort(403)

    done = db.session.scalar(
        db.select(LessonCompletion).where(
            LessonCompletion.student_id == g.user.id,
            LessonCompletion.lesson_id == lesson.id,
        )
    )
    if done:
        db.session.delete(done)
    else:
        db.session.add(LessonCompletion(student=g.user, lesson=lesson))
    db.session.flush()

    was_complete = enrollment.completed_at is not None
    enrollment.completed_at = utc_now() if enrollment.progress == 100 else None
    db.session.commit()
    if enrollment.completed_at and not was_complete:
        flash(f"You finished {course.title}. Well done!", "success")

    go_to = lesson
    if not done:
        i = course.lessons.index(lesson)
        if i + 1 < len(course.lessons):
            go_to = course.lessons[i + 1]
    return redirect(url_for("student.course_player", slug=course.slug, lesson=go_to.id))
