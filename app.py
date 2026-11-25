import os

import click
from flask import Flask, g, render_template, session
from flask_wtf.csrf import CSRFProtect

from config import Config
from helpers import slugify
from models import Course, Enrollment, Lesson, LessonCompletion, User, db
from routes import register_blueprints

csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    with app.app_context():
        db.create_all()

    register_blueprints(app)

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

    @app.template_filter("price")
    def format_price(value):
        return "Free" if not value else f"₹{value:,.0f}"

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
