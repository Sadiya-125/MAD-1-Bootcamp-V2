import os
import re
from functools import wraps
from urllib.parse import urlsplit

import click
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from flask_wtf.csrf import CSRFProtect

from config import Config
from models import (
    CATEGORIES,
    LEVELS,
    Course,
    Enrollment,
    Lesson,
    LessonCompletion,
    User,
    db,
    utc_now,
)


csrf = CSRFProtect()


SIGNUP_ROLES = ("student", "instructor")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.full_path))
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


def is_safe_next(target):
    if not target:
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc and target.startswith("/")


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    with app.app_context():
        db.create_all()

    @app.before_request
    def load_current_user():
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            user = db.session.get(User, user_id)

            if user is None or not user.is_active:
                session.clear()
            else:
                g.user = user

    @app.context_processor
    def inject_user():
        return {"current_user": g.get("user")}

    @app.route("/")
    def home():
        return redirect(url_for("course_list"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("dashboard"))

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
            return redirect(url_for("login"))

        return render_template("register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))

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
            return redirect(url_for("dashboard"))

        return render_template("login.html", identifier=identifier)

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = g.user
        if user.is_student:
            return redirect(url_for("student_dashboard"))
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

    @app.route("/instructor/area")
    @instructor_required
    def instructor_area():
        return render_template("role_check.html", area="Instructor")

    @app.route("/admin/area")
    @admin_required
    def admin_area():
        return render_template("role_check.html", area="Admin")

    @app.template_filter("price")
    def format_price(value):
        return "Free" if not value else f"₹{value:,.0f}"

    @app.route("/courses")
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

    @app.route("/courses/<slug>")
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

    @app.route("/search")
    def search():
        return redirect(url_for("course_list", **request.args))

    @app.route("/enroll/<int:course_id>", methods=["POST"])
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
        return redirect(url_for("course_player", slug=course.slug))

    @app.route("/student/dashboard")
    @student_required
    def student_dashboard():
        enrollments = sorted(
            g.user.enrollments, key=lambda e: e.enrolled_at, reverse=True
        )
        return render_template("student_dashboard.html", enrollments=enrollments)

    @app.route("/learn/<slug>")
    @student_required
    def course_player(slug):
        course = db.first_or_404(db.select(Course).where(Course.slug == slug))
        enrollment = get_enrollment(g.user.id, course.id)
        if enrollment is None:
            flash("Enroll in this course to start learning.", "warning")
            return redirect(url_for("course_detail", slug=course.slug))

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

    @app.route("/lesson/<int:lesson_id>/complete", methods=["POST"])
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
        return redirect(url_for("course_player", slug=course.slug, lesson=go_to.id))

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("403.html"), 403

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(username, email, password):
        email = email.strip().lower()
        exists = db.session.scalar(
            db.select(User).where((User.username == username) | (User.email == email))
        )
        if exists:
            raise click.ClickException("A user with that username or email exists.")
        admin = User(username=username, email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin '{username}' created.")

    @app.cli.command("seed")
    def seed():
        if db.session.scalar(db.select(Course)):
            click.echo("Database already has courses, skipping.")
            return

        def make_user(username, role):
            user = User(username=username, email=f"{username}@example.com", role=role)
            user.set_password("password123")
            db.session.add(user)
            return user

        make_user("admin", "admin")
        teacher = make_user("asha", "instructor")
        make_user("ravi", "student")

        demo = [
            ("Python for Beginners", "programming", "beginner", 0, True,
             "Write your first programs and learn how Python thinks.",
             ["Installing Python", "Variables and types", "If statements", "Loops", "Functions"]),
            ("Flask Web Development", "programming", "intermediate", 499, False,
             "Build and ship a real web app with Flask and SQLite.",
             ["Routes and views", "Templates with Jinja2", "Forms", "Databases with SQLAlchemy"]),
            ("UI Design Basics", "design", "beginner", 0, False,
             "Spacing, type and colour: the rules behind clean screens.",
             ["Visual hierarchy", "Typography", "Colour and contrast"]),
            ("Data Analysis with Pandas", "data", "intermediate", 799, False,
             "Clean, explore and chart real datasets with pandas.",
             ["DataFrames", "Cleaning data", "Grouping and joins", "Plotting"]),
            ("Starting a Small Business", "business", "advanced", 299, False,
             "From idea to first customer, step by step.",
             ["Finding an idea", "Pricing", "Your first sale"]),
        ]
        for title, category, level, price, featured, summary, lesson_titles in demo:
            course = Course(
                title=title,
                slug=slugify(title),
                short_description=summary,
                description=f"{summary}\n\nEach lesson is short and ends with a small exercise.",
                category=category,
                level=level,
                price=price,
                is_published=True,
                is_featured=featured,
                instructor=teacher,
            )
            course.lessons = [
                Lesson(
                    title=name,
                    order=i,
                    duration=10 + i * 5,
                    is_free_preview=(i == 1),
                    content=f"Notes for '{name}'.\n\nRead through, then try the exercise.",
                )
                for i, name in enumerate(lesson_titles, start=1)
            ]
            db.session.add(course)

        draft = Course(title="Advanced SQL (draft)", slug="advanced-sql-draft",
                       category="data", level="advanced", instructor=teacher)
        db.session.add(draft)
        db.session.commit()
        click.echo("Seeded 3 users (password: password123) and 6 courses.")

    @app.shell_context_processor
    def make_shell_context():
        return {
            "db": db,
            "User": User,
            "Course": Course,
            "Lesson": Lesson,
            "Enrollment": Enrollment,
            "LessonCompletion": LessonCompletion,
        }

    return app
