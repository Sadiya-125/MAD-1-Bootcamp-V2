# CourseHub

CourseHub is a small learning platform built with Flask. Instructors create courses and lessons, students enroll and track their progress, and an admin looks after users and content. It's the project for the MAD-1 Bootcamp V2, built one day at a time over seven days.

## Features

- **Accounts and roles:** register, log in and log out, with three roles (student, instructor and admin), each with its own dashboard
- **Course catalog:** public course listing with search, filters by category, level and price, and pagination
- **Course pages:** description, curriculum with free preview lessons, and an enroll button
- **Learning:** students enroll, open a course player, mark lessons complete and see a progress bar per course
- **Course builder:** instructors create courses, add, edit, order and delete lessons, and publish or unpublish
- **Admin panel:** platform stats, a popular-courses chart, user roles and deactivation, publishing and featuring any course
- **Profile:** update email, bio and avatar, and change password
- **Production basics:** 403, 404 and 500 pages, CSRF protection on every form, tests and a Procfile for deployment

## Tech stack

| Part | Tool |
|------|------|
| Language | Python 3.8 or newer |
| Web framework | Flask 3 |
| Database | SQLite through Flask-SQLAlchemy (SQLAlchemy 2.x) |
| Templates | Jinja2, plain CSS (no JavaScript) |
| Security | Werkzeug password hashing, Flask-WTF CSRF protection |
| Testing | pytest |
| Production server | gunicorn |

## Data model

| Model | What it stores | Relationships |
|-------|----------------|---------------|
| User | Students, instructors and admins (`role` column) | Teaches many courses; has many enrollments and completions |
| Course | Title, slug, description, price, category, level, published and featured flags | Belongs to one instructor; has many lessons |
| Lesson | Title, notes, video link, duration, position, free preview flag | Belongs to one course |
| Enrollment | Which student joined which course, and when they finished | Links User and Course (many-to-many); computes `progress` |
| LessonCompletion | Which student finished which lesson | Links User and Lesson |

A student can enroll in a course only once and complete a lesson only once. The database enforces both rules with unique constraints.

## Project structure

```
coursehub/
├── app.py                  # App factory, error pages, CLI commands
├── helpers.py              # Access decorators and small shared helpers
├── routes/                 # One Blueprint per area of the app
│   ├── __init__.py         # register_blueprints(app)
│   ├── auth.py             # Register, login, logout, dashboard, profile
│   ├── courses.py          # Home, catalog, course page, search
│   ├── student.py          # Enroll, My learning, course player
│   ├── instructor.py       # Course builder
│   └── admin.py            # Admin panel
├── models.py               # Database models
├── config.py               # Settings (secret key, database URL)
├── requirements.txt        # Python dependencies
├── pytest.ini              # Test settings
├── Procfile                # Start command for Render / Railway / Heroku
├── .env.example            # Template for your .env file
├── .gitignore
├── instance/
│   └── coursehub.db        # SQLite database (created automatically)
├── static/
│   └── style.css
├── templates/
│   ├── base.html           # Layout: navbar, flash messages, footer
│   ├── macros.html         # pagination, progress_bar, stat_card, admin_tabs
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   ├── course_list.html    # Catalog with search and filters
│   ├── course_detail.html  # Course page with curriculum and enroll button
│   ├── student_dashboard.html
│   ├── course_player.html
│   ├── instructor_dashboard.html
│   ├── course_builder.html # New / edit course form
│   ├── lesson_manager.html # Lessons of one course
│   ├── lesson_form.html    # New / edit lesson form
│   ├── admin_dashboard.html
│   ├── admin_users.html
│   ├── admin_courses.html
│   └── errors/
│       ├── 403.html
│       ├── 404.html
│       └── 500.html
└── tests/
    ├── conftest.py         # Test app, client and login fixtures
    └── test_app.py
```

The routes are split into Flask Blueprints, one file per area in `routes/`. A Blueprint's routes are named with its prefix, so templates link to them as `url_for('auth.login')`, `url_for('courses.course_list')`, `url_for('student.dashboard')` and so on.

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

### 4. Set a secret key

Copy `.env.example` to `.env`, then put a real value in it:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

If you skip this, the app uses a development key. That's fine on your own machine but never in production.

### 5. Add demo data (optional)

```bash
flask seed
```

This creates three users, all with the password `password123`:

| Username | Role |
|----------|------|
| admin | Admin |
| asha | Instructor |
| ravi | Student |

It also adds five published courses with lessons, and one draft.

### 6. Run the app

```bash
flask run --debug
```

Open http://127.0.0.1:5000. Flask finds the `create_app()` factory in `app.py` automatically, so you don't need to set `FLASK_APP`. The database tables are created the first time the app starts.

### 7. Create your own admin (optional)

Admins can't sign up through the website. Create one from the terminal:

```bash
flask create-admin
```

## Routes

| Method | Path | Access | What it does |
|--------|------|--------|--------------|
| GET | `/` | Public | Redirects to the catalog |
| GET | `/courses` | Public | Catalog with `q`, `category`, `level`, `price` and `page` |
| GET | `/courses/<slug>` | Public | Course page (drafts only for their instructor and admins) |
| GET | `/search` | Public | Redirects to the catalog with the same search |
| GET/POST | `/register` | Public | Sign up as a student or instructor |
| GET/POST | `/login` | Public | Log in with username or email |
| POST | `/logout` | Logged in | Log out |
| GET | `/dashboard` | Logged in | Sends each role to its own dashboard |
| GET/POST | `/profile` | Logged in | Edit email, bio and avatar |
| POST | `/profile/password` | Logged in | Change password |
| POST | `/enroll/<course_id>` | Student | Enroll in a published course |
| GET | `/student/dashboard` | Student | My courses with progress |
| GET | `/learn/<slug>` | Enrolled student | Course player (`?lesson=<id>` picks a lesson) |
| POST | `/lesson/<id>/complete` | Enrolled student | Mark a lesson done or not done |
| GET | `/instructor/dashboard` | Instructor | My courses with stats |
| GET/POST | `/instructor/course/new` | Instructor | Create a course (saved as a draft) |
| GET/POST | `/instructor/course/<id>/edit` | Course owner | Edit course details |
| GET | `/instructor/course/<id>/lessons` | Course owner | Manage lessons |
| POST | `/instructor/course/<id>/publish` | Course owner | Publish or unpublish |
| GET/POST | `/instructor/lesson/new?course_id=` | Course owner | Add a lesson |
| GET/POST | `/instructor/lesson/<id>/edit` | Course owner | Edit a lesson |
| POST | `/instructor/lesson/<id>/delete` | Course owner | Delete a lesson |
| GET | `/admin` | Admin | Stats, popular courses, recent enrollments |
| GET | `/admin/users` | Admin | All users, 20 per page |
| POST | `/admin/user/<id>/role` | Admin | Change a user's role |
| POST | `/admin/user/<id>/active` | Admin | Deactivate or reactivate a user |
| GET | `/admin/courses` | Admin | All courses, including drafts |
| POST | `/admin/course/<id>/publish` | Admin | Publish or unpublish any course |
| POST | `/admin/course/<id>/feature` | Admin | Feature a course at the top of the catalog |

## How security works

- Passwords are hashed with Werkzeug's `generate_password_hash`, never stored as plain text.
- After login, the user's id is kept in Flask's signed session cookie. Every request loads the user into `g.user`, and templates see it as `current_user`.
- `@login_required` sends visitors to the login page and brings them back afterwards. Only links inside this site are followed, so the `next` parameter can't redirect people elsewhere.
- `@student_required`, `@instructor_required` and `@admin_required` show a 403 page to anyone with the wrong role. Instructors can only change their own courses.
- Every POST form has a hidden CSRF token (Flask-WTF), so other websites can't submit forms on a user's behalf.
- Logout is a POST form, so a link on another site can't log people out.
- Nobody can pick "admin" on the sign-up form. Admins can't remove their own admin role or deactivate themselves.
- Deactivated accounts can't log in and are logged out on their next request.

## Running the tests

```bash
pytest
```

The tests use a fresh in-memory database each time, loaded with the same demo data as `flask seed`, so they never touch your real database. They cover sign-up, login, role checks, the catalog, enrollment and progress, the course builder and the admin panel.

## Deployment (Render)

1. Push the project to GitHub. `.env` and `instance/` are in `.gitignore`, so they stay on your machine.
2. On Render, create a **Web Service** from the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn "app:create_app()"` (the same line as in `Procfile`)
5. Under **Environment**, add `SECRET_KEY` with a long random value.
6. After the first deploy, open the **Shell** tab and run `flask seed` or `flask create-admin`.

Railway and Heroku read the `Procfile` directly, so only step 5 is needed there.

The free tiers of these services reset the disk on every deploy, which wipes the SQLite file. That's fine for a demo. For real use, add a persistent disk or point `DATABASE_URL` to a hosted database.

## Useful commands

| Command | What it does |
|---------|--------------|
| `flask run --debug` | Start the dev server with auto-reload |
| `flask seed` | Add demo users and courses |
| `flask create-admin` | Create an admin user |
| `flask shell` | Python shell with `db` and all models loaded |
| `pytest` | Run the tests |

To start over with an empty database, stop the server and delete `instance/coursehub.db`. It's recreated on the next run.

## Bootcamp progress

| Day | Topic | Status |
|-----|-------|--------|
| 1 | Project setup and database models | Done |
| 2 | Authentication and roles | Done |
| 3 | Course catalog, search and CSRF protection | Done |
| 4 | Enrollment, course player and progress | Done |
| 5 | Instructor course builder | Done |
| 6 | Admin panel and stats | Done |
| 7 | Error pages, profile, tests and deployment | Done |

## Ideas for later

Payments (Stripe), certificates as PDFs, quizzes, lesson comments, video hosting and email notifications are all good next steps. None of them are needed for the core project.

## Troubleshooting

**`flask: command not found`**: the virtual environment isn't active, or the install didn't finish. Activate the venv and run `pip install -r requirements.txt` again.

**`Error: Could not locate a Flask application`**: run `flask` from inside the `coursehub` folder, where `app.py` is.

**`Bad Request: The CSRF token is missing`**: a `<form method="post">` is missing its hidden `csrf_token` line. Copy it from any other form.

**`sqlite3.OperationalError: no such column`**: you changed a model after the database was created. `db.create_all()` only creates missing tables; it doesn't change existing ones. Delete `instance/coursehub.db` and restart.

**Port 5000 already in use** (common on macOS, where AirPlay uses it): run `flask run --port 5001`.