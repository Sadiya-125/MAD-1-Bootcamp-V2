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

    @app.route("/student/area")
    @student_required
    def student_area():
        return render_template("role_check.html", area="Student")

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
        return render_template("course_detail.html", course=course)

    @app.route("/search")
    def search():
        return redirect(url_for("course_list", **request.args))

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
