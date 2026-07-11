# Aniket.ProjectMate — Learning Platform

Production-ready full-stack learning platform for students: free & paid classes, attendance, rewards, referrals, announcements, and automated emails.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | HTML5, CSS3, Bootstrap 5, HTMX, Alpine.js, Font Awesome |
| Backend | Django 5/6, Django REST Framework |
| DB | SQLite (dev) · PostgreSQL (prod) |
| Async | Celery + Redis |
| Media | Local / Cloudinary / S3 |
| Deploy | Docker · Gunicorn · WhiteNoise · Render |

## Quick start (local)

```bash
# 1. Clone & enter
cd aniket.projectmate

# 2. Create venv & install
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# 3. Environment
copy .env.example .env   # Windows
# cp .env.example .env   # Unix

# 4. Migrate & seed
python manage.py migrate
python manage.py seed_data

# 5. Run
python manage.py runserver
```

Open http://127.0.0.1:8000

### Demo accounts (after seed)

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@projectmate.local (username: `admin`) | Aniket@9096 |
| Student | student@projectmate.local | student12345 |

Admin panel: http://127.0.0.1:8000/admin/

## Project structure

```
apps/
  accounts/       # User, profile, auth, dashboard
  core/           # Landing, settings, FAQ, gallery
  classes/        # Free classes & registration
  courses/        # Paid courses (payment future-ready)
  announcements/  # News & pinned updates
  attendance/     # Marking + consistency rewards
  rewards/        # Points, badges, resume review
  referrals/      # Referral codes + admin approval
  feedback/       # Testimonials (moderation)
  notifications/  # Email templates, logs, in-app alerts
  api/            # DRF REST API (v1)
config/           # Settings, Celery, URLs
templates/        # Reusable premium UI
static/           # CSS / JS
```

## API (DRF)

Base: `/api/v1/`

- `POST /auth/login/` — token auth
- `GET /dashboard/` — student snapshot
- `GET /announcements/`, `/classes/`, `/courses/`
- `POST /classes/{slug}/register/`
- `GET /attendance/`, `/rewards/`, `/referrals/`, `/notifications/`
- `GET|POST /feedback/`
- `GET /leaderboard/`
- `GET /students/` (admin)

Browsable API: `/api/v1/` when authenticated.

## Celery

```bash
# Terminal 1 — Redis must be running
celery -A config worker -l info

# Terminal 2 — scheduled reminders
celery -A config beat -l info
```

Task: `send_class_reminders` — emails for classes within 24h.

## Docker

```bash
docker compose up --build
```

Services: `web`, `db` (Postgres), `redis`, `worker`, `beat`.

## Render deployment

1. Push repo to GitHub.
2. Connect on [Render](https://render.com) using `render.yaml`, or create a Web Service manually:
   - Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
   - Env: `DJANGO_SETTINGS_MODULE=config.settings`, `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`, `REDIS_URL`, SMTP vars.
3. Run migrate via Render shell: `python manage.py migrate && python manage.py seed_data`

## Environment variables

See `.env.example` for full list: `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, SMTP, Cloudinary/S3, Google OAuth.

## Features map

- Landing (no login): hero, announcements, free/paid classes, stats, testimonials, FAQ, mentor, gallery, contact
- Auth: email login, Google (allauth), trust message, forgot password, OTP-ready fields
- Dashboard: profile, classes, attendance, rewards, referrals, certificates, resume, notifications
- Admin: full CRUD, referral approval, attendance actions, email templates, site settings
- Automation: registration email + ICS, reminders (Celery), consistency reward at 6 sessions

## License

Private — Aniket.ProjectMate
