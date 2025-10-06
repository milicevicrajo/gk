from pathlib import Path
import os
import environ
import dj_database_url
import shutil

BASE_DIR = Path(__file__).resolve().parent.parent

# .env loader: prvo ENV_FILE, pa .env / .env.production / .env.development
# ── .env loader sa evidencijom izvora ───────────────────────────────────────
env = environ.Env()
ENV_SOURCE = None  # <<— OVDE ćemo zapamtiti odakle je čitano

ENV_FILE = os.getenv("ENV_FILE")
if ENV_FILE:
    env.read_env(ENV_FILE)
    ENV_SOURCE = f"ENV_FILE={ENV_FILE}"
else:
    for name in (".env", ".env.production", ".env.development"):
        p = BASE_DIR / name
        if p.exists():
            env.read_env(str(p))
            ENV_SOURCE = f"AUTO={p}"
            break
    if ENV_SOURCE is None:
        ENV_SOURCE = "NONE (samo process env varijable)"

# (opciono) uključi “bučan” ispis samo kad želiš
if env.bool("ENV_DEBUG", default=False):
    print(f"[settings] BASE_DIR={BASE_DIR}")
    print(f"[settings] ENV source → {ENV_SOURCE}")


# Core
DEBUG = env.bool("DEBUG", default=False)
SECRET_KEY = env.str("SECRET_KEY", default="CHANGE_ME_DEV_ONLY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# Security
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=not DEBUG)
SESSION_COOKIE_SAMESITE = env.str("SESSION_COOKIE_SAMESITE", default="Lax")
X_FRAME_OPTIONS = "SAMEORIGIN"

# ako si iza Nginx/CloudPanel proxy-ja:
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Apps
INSTALLED_APPS = [
    "django.contrib.admin", 
    "django.contrib.auth", 
    "django.contrib.contenttypes",
    "django.contrib.sessions", 
    "django.contrib.messages", 
    "django.contrib.staticfiles",
    "core", 
    "django_select2", 
    "widget_tweaks",
    "django_filters",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gk.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "gk.wsgi.application"

# Database
print(f"DEBUGGING CHECK: DATABASE_URL is set to -> {os.environ.get('DATABASE_URL')}")

DATABASE_URL = env.str("DATABASE_URL", default="sqlite:///db.sqlite3")
DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}

# I18N / TZ
LANGUAGE_CODE = env.str("LANGUAGE_CODE", default="en-us")  # ili "sr-Latn"
TIME_ZONE = env.str("TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

# Static & Media
STATIC_URL = "static/"

# Ako je u .env vrednost prazna, padni na default putanju u projektu
STATIC_ROOT = env.str("STATIC_ROOT", default="") or str(BASE_DIR / "staticfiles")
MEDIA_URL  = env.str("MEDIA_URL",  default="/media/")
MEDIA_ROOT = env.str("MEDIA_ROOT", default="") or str(BASE_DIR / "media")
STATICFILES_DIRS = [BASE_DIR / "static"]  # ne mešati sa STATIC_ROOT!
# Auth redirects
LOGIN_URL = "core:login"
LOGIN_REDIRECT_URL = "core:index"
LOGOUT_REDIRECT_URL = "core:login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# WKHTMLTOPDF_CMD = shutil.which("wkhtmltopdf")
# Ako NISI dodao u PATH, postavi punu putanju:
WKHTMLTOPDF_CMD = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"

PDFKIT_OPTIONS = {
    "page-size": "A4",
    "margin-top": "10mm",
    "margin-right": "10mm",
    "margin-bottom": "12mm",
    "margin-left": "10mm",
    "encoding": "UTF-8",
    "enable-local-file-access": None,  # važno za CSS/IMG iz static/
}