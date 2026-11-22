from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


ROLES = ("student", "instructor", "admin")
LEVELS = ("beginner", "intermediate", "advanced")
CATEGORIES = ("programming", "design", "business", "data")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=utc_now)
    is_active = db.Column(db.Boolean, default=True)

    taught_courses = db.relationship("Course", backref="instructor", lazy=True)

    enrollments = db.relationship(
        "Enrollment", backref="student", cascade="all, delete-orphan"
    )
    completions = db.relationship(
        "LessonCompletion", backref="student", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_student(self):
        return self.role == "student"

    @property
    def is_instructor(self):
        return self.role == "instructor"

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    short_description = db.Column(db.String(500))
    thumbnail = db.Column(db.String(300))
    price = db.Column(db.Float, default=0.0)
    category = db.Column(db.String(50))
    level = db.Column(db.String(20))
    is_published = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    lessons = db.relationship(
        "Lesson",
        backref="course",
        cascade="all, delete-orphan",
        order_by="Lesson.order",
    )
    enrollments = db.relationship(
        "Enrollment", backref="course", cascade="all, delete-orphan"
    )

    @property
    def students(self):
        return [enrollment.student for enrollment in self.enrollments]

    def __repr__(self):
        return f"<Course {self.slug}>"


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    video_url = db.Column(db.String(300))
    duration = db.Column(db.Integer)
    order = db.Column(db.Integer, default=0)
    is_free_preview = db.Column(db.Boolean, default=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)

    completions = db.relationship(
        "LessonCompletion", backref="lesson", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Lesson {self.order}: {self.title}>"


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=utc_now)
    completed_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="unique_enrollment"),
    )

    @property
    def progress(self):
        total = db.session.scalar(
            db.select(db.func.count(Lesson.id)).where(
                Lesson.course_id == self.course_id
            )
        )
        if not total:
            return 0
        completed = db.session.scalar(
            db.select(db.func.count(LessonCompletion.id))
            .join(Lesson)
            .where(
                LessonCompletion.student_id == self.student_id,
                Lesson.course_id == self.course_id,
            )
        )
        return round(completed / total * 100)

    def __repr__(self):
        return f"<Enrollment user={self.student_id} course={self.course_id}>"


class LessonCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)
    completed_at = db.Column(db.DateTime, default=utc_now)

    __table_args__ = (
        db.UniqueConstraint("student_id", "lesson_id", name="unique_completion"),
    )

    def __repr__(self):
        return f"<LessonCompletion user={self.student_id} lesson={self.lesson_id}>"
