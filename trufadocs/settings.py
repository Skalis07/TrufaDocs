"""Django settings for trufadocs project."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga simple de variables desde .env (solo en local)
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

def _get_env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def _get_env_list(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


# Claves y flags principales (se sobreescriben via .env)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-change-me")

DEBUG = _get_env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = _get_env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1",
)

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "editor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "trufadocs.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    }
]

WSGI_APPLICATION = "trufadocs.wsgi.application"

DATABASES = {
    "default": {
        # Proyecto sin base de datos real (no guardar datos)
        "ENGINE": "django.db.backends.dummy",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "es"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Limites y rutas configurables por entorno
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
CV_TEMPLATE_PATH = os.environ.get("CV_TEMPLATE_PATH", "")

FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------
# Seguridad / Produccion
# -----------------------

# Ajustes basicos de seguridad (validos tambien en local)
CSRF_TRUSTED_ORIGINS = _get_env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    # En produccion exigimos variables reales y HTTPS
    if SECRET_KEY == "django-insecure-change-me":
        raise ImproperlyConfigured("DJANGO_SECRET_KEY es requerido en produccion.")
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS es requerido en produccion.")

    SECURE_SSL_REDIRECT = _get_env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = _get_env_bool("DJANGO_SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = _get_env_bool("DJANGO_CSRF_COOKIE_SECURE", True)

    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _get_env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = _get_env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)

    if _get_env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = _get_env_bool("DJANGO_USE_X_FORWARDED_HOST", False)
