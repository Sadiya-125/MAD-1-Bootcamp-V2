# CourseHub

CourseHub is a small learning platform built with Flask. Instructors create courses and lessons, students enroll and track their progress, and an admin looks after users and content. It's the project for the MAD-1 Bootcamp V2, built one day at a time over seven days.

## Features

When the project is finished, it will have:

- **Accounts and roles:** register, log in and log out, with three roles (student, instructor and admin), each seeing a different dashboard
- **Course catalog:** public course listing with search and filters by category, level and price
- **Enrollment and progress:** students enroll, open a course player, mark lessons complete and see a progress bar per course
- **Course builder:** instructors create courses, add and order lessons, and publish or unpublish them
- **Admin panel:** user management, course moderation and platform stats
- **Production basics:** error pages, CSRF protection, pagination, tests and deployment config

## Tech stack

| Part             | Tool                                             |
| ---------------- | ------------------------------------------------ |
| Language         | Python 3.8 or newer                              |
| Web framework    | Flask 3                                          |
| Database         | SQLite through Flask-SQLAlchemy (SQLAlchemy 2.x) |
| Templates        | Jinja2                                           |
| Password hashing | Werkzeug                                         |
| Config           | python-dotenv                                    |

## Data model

| Model            | What it stores                                                    | Relationships                                              |
| ---------------- | ----------------------------------------------------------------- | ---------------------------------------------------------- |
| User             | Students, instructors and admins (`role` column)                  | Teaches many courses; has many enrollments and completions |
| Course           | Title, slug, description, price, category, level, published state | Belongs to one instructor; has many lessons                |
| Lesson           | Title, content, video URL, duration, order                        | Belongs to one course                                      |
| Enrollment       | Which student joined which course, and when                       | Links User and Course (many-to-many); computes `progress`  |
| LessonCompletion | Which student finished which lesson                               | Links User and Lesson                                      |

A student can enroll in a course only once and complete a lesson only once. The database enforces both rules with unique constraints.

## Project structure

```
coursehub/
├── app.py              # App factory, routes, access decorators, CLI commands
├── models.py           # Database models
├── config.py           # Settings (secret key, database URL)
├── requirements.txt    # Python dependencies
├── .gitignore
├── .env                # Your local secrets (optional, not committed)
├── instance/
│   └── coursehub.db    # SQLite database (created automatically)
├── templates/          # Jinja2 HTML templates
└── static/             # CSS and JavaScript
```

## Setup

### 1. Get the code

Unzip the project, or clone it, and open a terminal in the `coursehub` folder.

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
# macOS / Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

You'll see `(venv)` at the start of your terminal line when it's active.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set a secret key (recommended)

Create a file named `.env` in the project folder:

```
SECRET_KEY=replace-this-with-a-long-random-string
```

You can generate a good value with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

If you skip this step, the app uses a development key. That's fine on your own machine but never in production.

You can also set `DATABASE_URL` in `.env` to use a different database. By default it's SQLite at `instance/coursehub.db`.

### 5. Run the app

```bash
flask run
```

Open http://127.0.0.1:5000 in your browser. Flask finds the `create_app()` factory in `app.py` automatically, so you don't need to set `FLASK_APP`.

For auto-reload while you edit code:

```bash
flask run --debug
```

The database tables are created the first time the app starts.

### 6. Create an admin account

Admins can't sign up through the website. Create one from the terminal:

```bash
flask create-admin
```

It asks for a username, email and password.

## Useful commands

| Command              | What it does                                         |
| -------------------- | ---------------------------------------------------- |
| `flask run --debug`  | Start the dev server with auto-reload                |
| `flask shell`        | Python shell with `db` and all models already loaded |
| `flask create-admin` | Create an admin user                                 |

To start over with an empty database, stop the server and delete `instance/coursehub.db`. It's recreated on the next run.

## Trying it in the shell

```bash
flask shell
```

```python
teacher = User(username="asha", email="asha@example.com", role="instructor")
teacher.set_password("pass12345")
student = User(username="ravi", email="ravi@example.com")
student.set_password("pass12345")
db.session.add_all([teacher, student])
db.session.commit()

course = Course(title="Python Basics", slug="python-basics",
                level="beginner", category="programming", instructor=teacher)
course.lessons = [Lesson(title="Variables", order=1),
                  Lesson(title="Loops", order=2)]
db.session.add(course)
db.session.commit()

enrollment = Enrollment(student=student, course=course)
db.session.add(enrollment)
db.session.add(LessonCompletion(student=student, lesson=course.lessons[0]))
db.session.commit()

course.students        # [<User ravi (student)>]
enrollment.progress    # 50
```

## Bootcamp progress

| Day | Topic                             | Status      |
| --- | --------------------------------- | ----------- |
| 1   | Project setup and database models | Done        |
| 2   | Authentication and roles          | In progress |
| 3   | Course catalog and public pages   | Not started |
| 4   | Enrollment and student dashboard  | Not started |
| 5   | Instructor course builder         | Not started |
| 6   | Admin panel and analytics         | Not started |
| 7   | Polish, tests and deployment      | Not started |

## Troubleshooting

**`flask: command not found`**: the virtual environment isn't active, or the install didn't finish. Activate the venv and run `pip install -r requirements.txt` again.

**`Error: Could not locate a Flask application`**: run `flask` from inside the `coursehub` folder, where `app.py` is.

**`sqlite3.OperationalError: no such column`**: you changed a model after the database was created. `db.create_all()` only creates missing tables; it doesn't change existing ones. Delete `instance/coursehub.db` and restart the app.

**Port 5000 already in use** (common on macOS, where AirPlay uses it): run `flask run --port 5001`.
