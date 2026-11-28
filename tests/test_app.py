from models import Course, Enrollment, User, db


def get_course(app, slug):
    with app.app_context():
        return db.session.scalar(db.select(Course).where(Course.slug == slug))


def test_register_and_login(client, login):
    response = client.post("/register", data={
        "username": "meera", "email": "meera@example.com",
        "password": "secret123", "confirm_password": "secret123", "role": "student",
    })
    assert response.status_code == 302

    response = login("meera", "secret123")
    assert response.headers["Location"].endswith("/dashboard")


def test_register_rejects_admin_role(client):
    response = client.post("/register", data={
        "username": "sneaky", "email": "s@example.com",
        "password": "secret123", "confirm_password": "secret123", "role": "admin",
    })
    assert response.status_code == 400


def test_wrong_password(login):
    assert login("ravi", "nope").status_code == 401


def test_protected_page_needs_login(client):
    response = client.get("/student/dashboard")
    assert "/login" in response.headers["Location"]


def test_roles_are_enforced(client, login):
    login("ravi")
    assert client.get("/instructor/dashboard").status_code == 403
    assert client.get("/admin").status_code == 403


def test_catalog_hides_drafts(client):
    page = client.get("/courses").get_data(as_text=True)
    assert "Python for Beginners" in page
    assert "Advanced SQL" not in page


def test_search(client):
    page = client.get("/courses?q=pandas").get_data(as_text=True)
    assert "Data Analysis with Pandas" in page
    assert "Python for Beginners" not in page


def test_missing_course_is_404(client):
    assert client.get("/courses/does-not-exist").status_code == 404


def test_enroll_and_track_progress(app, client, login):
    course = get_course(app, "python-for-beginners")
    login("ravi")

    client.post(f"/enroll/{course.id}")
    with app.app_context():
        lesson_ids = [l.id for l in db.session.get(Course, course.id).lessons]
    client.post(f"/lesson/{lesson_ids[0]}/complete")

    with app.app_context():
        enrollment = db.session.scalar(db.select(Enrollment))
        assert enrollment.progress == 20


def test_cannot_enroll_twice(app, client, login):
    course = get_course(app, "python-for-beginners")
    login("ravi")
    client.post(f"/enroll/{course.id}")
    client.post(f"/enroll/{course.id}")
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Enrollment.id))) == 1


def test_instructor_builds_and_publishes_course(app, client, login):
    login("asha")
    client.post("/instructor/course/new", data={
        "title": "Git Basics", "category": "programming", "level": "beginner", "price": "0",
    })
    course = get_course(app, "git-basics")
    assert course is not None and not course.is_published

    client.post(f"/instructor/lesson/new?course_id={course.id}", data={"title": "Commits"})
    client.post(f"/instructor/course/{course.id}/publish")

    assert "Git Basics" in client.get("/courses").get_data(as_text=True)


def test_admin_changes_role(app, client, login):
    with app.app_context():
        ravi_id = db.session.scalar(db.select(User.id).where(User.username == "ravi"))
    login("admin")
    client.post(f"/admin/user/{ravi_id}/role", data={"role": "instructor"})
    with app.app_context():
        assert db.session.get(User, ravi_id).role == "instructor"