"""
One settings module driven entirely by environment variables (see .env.example).

Memory notes for a single small server:
- No Redis, Celery or DRF. Background work runs in one `manage.py runworker` process.
- The cache is file based, so gunicorn workers and the task worker share it without a daemon.
- Heavy libraries (Pillow, boto3) are imported lazily where possible.
"""

import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from .env import env, env_bool, env_int, env_list, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = env_bool("DEBUG", False)
SECRET_KEY = env("SECRET_KEY", "dev-insecure-change-me" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set when DEBUG is off")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
# Public origin of this backend, used to build absolute media and download URLs.
API_URL = env("API_URL", "http://localhost:8000").rstrip("/")
# Public origin of the website, used in delivery messages and CORS.
SITE_URL = env("SITE_URL", "http://localhost:8080").rstrip("/")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", SITE_URL)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", API_URL)

INSTALLED_APPS = [
    "spectrum.apps.SpectrumAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.content",
    "apps.catalog",
    "apps.portal",
    "apps.orders",
]

MIDDLEWARE = [
    "apps.core.http.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "spectrum.urls"
WSGI_APPLICATION = "spectrum.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-wide admin template overrides (e.g. admin/change_list.html),
        # ahead of the admin app's own templates.
        "DIRS": [BASE_DIR / "spectrum" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]


def _database(url: str) -> dict:
    if not url or url.startswith("sqlite"):
        path = url.split("///", 1)[1] if url and "///" in url else str(BASE_DIR / "var" / "db.sqlite3")
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": path,
            "OPTIONS": {
                # WAL lets the web process read while the worker writes.
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000;",
                "transaction_mode": "IMMEDIATE",
            },
        }
    parts = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parts.path.lstrip("/"),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }


DATABASES = {"default": _database(env("DATABASE_URL"))}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": env("CACHE_DIR", str(BASE_DIR / "var" / ("cache-test" if "test" in sys.argv[1:2] else "cache"))),
        "TIMEOUT": 60 * 60 * 24,
        "OPTIONS": {"MAX_ENTRIES": 20000},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "var" / "static"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
# Hashed static file names (bulk-uploader.<hash>.js), so nginx's month-long
# /static/ cache can never serve a stale admin script after a deploy. Tests
# render admin pages without running collectstatic, so they keep plain names;
# with DEBUG on, Django bypasses the manifest by itself.
STATICFILES_BACKEND = (
    "django.contrib.staticfiles.storage.StaticFilesStorage" if TESTING
    else "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
)
if TESTING:
    import tempfile

    MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="spectrum-test-media-"))

USE_S3 = env_bool("USE_S3", False)
# Lifetime of signed download links. Each click mints a fresh one after the purchase check, so keep it short.
PRIVATE_URL_EXPIRE = int(env("PRIVATE_URL_EXPIRE", "300"))
if USE_S3:
    _s3 = {
        "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
        "region_name": env("AWS_S3_REGION_NAME", "ap-south-1"),
        "endpoint_url": env("AWS_S3_ENDPOINT_URL") or None,
        "signature_version": "s3v4",
        "file_overwrite": False,
    }
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                **_s3,
                "location": "public",
                "default_acl": env("AWS_PUBLIC_ACL", "public-read") or None,
                "querystring_auth": False,
                "custom_domain": env("AWS_S3_CUSTOM_DOMAIN") or None,
                "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
            },
        },
        "private": {
            "BACKEND": "storages.backends.s3.S3Storage",
            # max_memory_size: spill downloaded originals to disk above 2 MB instead of RAM.
            "OPTIONS": {**_s3, "location": "private", "default_acl": "private", "querystring_auth": True,
                        "querystring_expire": PRIVATE_URL_EXPIRE, "max_memory_size": 2 * 1024 * 1024},
        },
        "staticfiles": {"BACKEND": STATICFILES_BACKEND},
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(MEDIA_ROOT / "public"), "base_url": "/media/public/"},
        },
        "private": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(MEDIA_ROOT / "private"), "base_url": None},
        },
        "staticfiles": {"BACKEND": STATICFILES_BACKEND},
    }
# Serve local public media from Django (dev, or a server without S3 behind nginx).
SERVE_LOCAL_MEDIA = not USE_S3

# Uploads: large files stream to a temp file on disk instead of RAM.
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000
UPLOAD_MAX_BYTES = env_int("UPLOAD_MAX_BYTES", 40 * 1024 * 1024)

# Background tasks. Eager runs them inline after commit (handy in dev without a worker).
TASKS_EAGER = env_bool("TASKS_EAGER", DEBUG)

# Portal tokens (signed with SECRET_KEY, no extra dependency).
PORTAL_ACCESS_TTL = env_int("PORTAL_ACCESS_TTL", 30 * 60)
PORTAL_REFRESH_TTL = env_int("PORTAL_REFRESH_TTL", 14 * 24 * 3600)

# Payments and delivery.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET")
PAYMENTS_MOCK = env_bool("PAYMENTS_MOCK", DEBUG and not RAZORPAY_KEY_ID)
if PAYMENTS_MOCK and not DEBUG and not env_bool("ALLOW_MOCK_PAYMENTS", False):
    # Mock mode marks any order paid on request. Never let it reach a live site by accident.
    raise RuntimeError("PAYMENTS_MOCK is on while DEBUG is off. Set Razorpay keys, or ALLOW_MOCK_PAYMENTS=1 for a demo server.")
# Serve private downloads through nginx (X-Accel-Redirect) instead of tying up a gunicorn thread.
PRIVATE_ACCEL_PREFIX = env("PRIVATE_ACCEL_PREFIX", "" if DEBUG else "/_private/")
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = env("TWILIO_WHATSAPP_FROM")  # e.g. +14155238886
TWILIO_CONTENT_SID = env("TWILIO_CONTENT_SID")  # approved template; blank sends plain text (sandbox)
ORDER_ZIP_MAX_ITEMS = env_int("ORDER_ZIP_MAX_ITEMS", 400)
ORDER_ZIP_KEEP_DAYS = env_int("ORDER_ZIP_KEEP_DAYS", 30)
# Large temporary files (order zips) go on disk here, never in /tmp, which may be RAM.
WORK_DIR = Path(env("WORK_DIR", str(BASE_DIR / "var" / "tmp")))
WORK_DIR.mkdir(parents=True, exist_ok=True)
FILE_UPLOAD_TEMP_DIR = str(WORK_DIR)

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Spectrum <support@spectrum.in>")
ENQUIRY_NOTIFY_EMAILS = env_list("ENQUIRY_NOTIFY_EMAILS")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
