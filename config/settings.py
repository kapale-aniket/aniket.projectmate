"""Aniket.ProjectMate — single settings module (env-driven)."""
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    SECURE_SSL_REDIRECT=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me-projectmate-2026")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "*"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
CSRF_FAILURE_VIEW = "apps.core.errors.csrf_failure"

SITE_NAME = env("SITE_NAME", default="Aniket.ProjectMate")
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_filters",
    "django_htmx",
    "django_celery_beat",
    "django_celery_results",
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "apps.accounts.apps.AccountsConfig",
    "apps.core.apps.CoreConfig",
    "apps.classes.apps.ClassesConfig",
    "apps.courses.apps.CoursesConfig",
    "apps.announcements.apps.AnnouncementsConfig",
    "apps.attendance.apps.AttendanceConfig",
    "apps.rewards.apps.RewardsConfig",
    "apps.referrals.apps.ReferralsConfig",
    "apps.feedback.apps.FeedbackConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.api.apps.ApiConfig",
    "apps.adminpanel.apps.AdminpanelConfig",
    "apps.linkedin.apps.LinkedinConfig",
    "apps.naukri.apps.NaukriConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.core.middleware.EnsureCsrfCookieMiddleware",
    "apps.core.middleware.AdminNoCacheMiddleware",
    "apps.core.middleware.ActivityLogMiddleware",
    "apps.core.middleware.ThemeMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "apps.core.context_processors.site_settings",
                "apps.core.context_processors.theme",
                "apps.notifications.context_processors.unread_notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = env("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

from django.contrib.messages import constants as message_constants

MESSAGE_TAGS = {
    message_constants.DEBUG: "info",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

MEDIA_STORAGE = env("MEDIA_STORAGE", default="local")
if MEDIA_STORAGE == "cloudinary":
    INSTALLED_APPS += ["cloudinary", "cloudinary_storage"]
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME", default=""),
        "API_KEY": env("CLOUDINARY_API_KEY", default=""),
        "API_SECRET": env("CLOUDINARY_API_SECRET", default=""),
    }
    STORAGES["default"] = {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}
elif MEDIA_STORAGE == "s3":
    INSTALLED_APPS += ["storages"]
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
    AWS_DEFAULT_ACL = "public-read"
    AWS_QUERYSTRING_AUTH = False
    STORAGES["default"] = {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "core:home"

SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.AllowInactiveStudentBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
# Skip allauth "Sign In Via Google / Continue" interstitial — go straight to Google
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.ProjectMateSocialAccountAdapter"
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "select_account"},
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID", default=""),
            "secret": env("GOOGLE_CLIENT_SECRET", default=""),
            "key": "",
        },
        "OAUTH_PKCE_ENABLED": True,
    }
}
GOOGLE_OAUTH_CONFIGURED = bool(
    env("GOOGLE_CLIENT_ID", default="").strip()
    and env("GOOGLE_CLIENT_SECRET", default="").strip()
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "100/hour", "user": "1000/hour"},
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default='"Aniket.ProjectMate" <noreply@projectmate.local>',
)

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "projectmate",
        }
    }

if not CELERY_BROKER_URL:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"

SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE")
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REWARD_POINTS = {
    "attend_class": 50,
    "attend_class_active": 75,  # Active in session — more than present
    "daily_login": 5,
    "profile_completed": 100,
    "feedback_submitted": 25,
    "referral_approved": 200,
    "workshop_completed": 150,
    "resume_uploaded": 30,
}
CONSECUTIVE_ATTENDANCE_REWARD = 6

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "projectmate.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "apps": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

(BASE_DIR / "logs").mkdir(exist_ok=True)
INTERNAL_IPS = ["127.0.0.1"]

# ProjectMateBot — offline knowledge base only (no paid API key)

# LinkedIn automation (admin panel)
LINKEDIN_AUTOMATION_ROOT = BASE_DIR / "apps" / "linkedin" / "automation"
LINKEDIN_DATA_DIR = BASE_DIR / "data" / "linkedin"
LINKEDIN_DATA_DIR.mkdir(parents=True, exist_ok=True)
(LINKEDIN_AUTOMATION_ROOT / "job" / "output").mkdir(parents=True, exist_ok=True)
(LINKEDIN_AUTOMATION_ROOT / "connections" / "new_connection").mkdir(parents=True, exist_ok=True)
(LINKEDIN_AUTOMATION_ROOT / "posts" / "output").mkdir(parents=True, exist_ok=True)

# Naukri automation (admin panel)
NAUKRI_AUTOMATION_ROOT = BASE_DIR / "apps" / "naukri" / "automation"
NAUKRI_DATA_DIR = BASE_DIR / "data" / "naukri"
NAUKRI_DATA_DIR.mkdir(parents=True, exist_ok=True)
(NAUKRI_AUTOMATION_ROOT / "output").mkdir(parents=True, exist_ok=True)
