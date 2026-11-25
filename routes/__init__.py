from routes.admin import bp as admin_bp
from routes.auth import bp as auth_bp
from routes.courses import bp as courses_bp
from routes.instructor import bp as instructor_bp
from routes.student import bp as student_bp


def register_blueprints(app):
    for blueprint in (auth_bp, courses_bp, student_bp, instructor_bp, admin_bp):
        app.register_blueprint(blueprint)
