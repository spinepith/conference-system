from pathlib import Path
import os
import sys

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent       # conference-system/src/system
SRC_ROOT = BASE_DIR.parent                             # conference-system/src
PROJECT_ROOT = SRC_ROOT.parent                         # conference-system
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE, override=False)


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def resolve_project_path(*variable_names: str, default: Path) -> Path:
    raw_value = _first_env(*variable_names)
    path = Path(raw_value) if raw_value else Path(default)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def configure_external_package(package_name: str, path: Path, env_name: str) -> None:
    if not (path / "__init__.py").exists():
        raise ImproperlyConfigured(
            f"Не найден модуль {package_name}. Проверьте {env_name} в {ENV_FILE}. "
            f"Текущий путь: {path}"
        )
    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)


DOCX_PROCESSING_ROOT = resolve_project_path(
    "PATH_MODULE_DOCX_PROCESSING",
    "PATH_MODULE_DOCX_PROCESSONG",
    "DOCX_PROCESSING_ROOT",
    default=SRC_ROOT / "docx_processing",
)
TEMA_ROOT = resolve_project_path(
    "PATH_MODULE_TEMA",
    "TEMA_ROOT",
    default=SRC_ROOT / "tema",
)

CONTENT_VALIDATION_ROOT = resolve_project_path(
    "PATH_MODULE_CONTENT_VALIDATION",
    default=SRC_ROOT / "content-validation",
)
CONTENT_VALIDATION_API_URL = os.getenv(
    "CONTENT_VALIDATION_API_URL",
    "http://127.0.0.1:5100",
).rstrip("/")
CONTENT_VALIDATION_TIMEOUT = int(os.getenv("CONTENT_VALIDATION_TIMEOUT", "360"))
CONTENT_VALIDATION_ENABLED = os.getenv(
    "CONTENT_VALIDATION_ENABLED",
    "1",
).strip().lower() in {"1", "true", "yes", "on"}
configure_external_package("docx_processing", DOCX_PROCESSING_ROOT, "PATH_MODULE_DOCX_PROCESSING")
configure_external_package("tema", TEMA_ROOT, "PATH_MODULE_TEMA")

STORAGE_ROOT = resolve_project_path("PATH_STORAGE", "STORAGE_ROOT", default=PROJECT_ROOT / "storage")
LOGS_ROOT = resolve_project_path("PATH_LOGS", default=STORAGE_ROOT / "logs")
TEMPLATES_ROOT = resolve_project_path(
    "PATH_TEMPLATES",
    default=STORAGE_ROOT / "templates",
)
CONFERENCE_TEMPLATE_PATH = resolve_project_path(
    "PATH_CONFERENCE_TEMPLATE",
    "CONFERENCE_TEMPLATE_PATH",
    default=TEMPLATES_ROOT / "conference_template_v1.docx",
)
SUBMISSIONS_STORAGE_DIR = resolve_project_path(
    "SUBMISSIONS_STORAGE_DIR",
    default=STORAGE_ROOT / "submissions",
)
ISSUES_STORAGE_DIR = resolve_project_path(
    "ISSUES_STORAGE_DIR",
    default=STORAGE_ROOT / "issues",
)

for directory in (STORAGE_ROOT, LOGS_ROOT, SUBMISSIONS_STORAGE_DIR, ISSUES_STORAGE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

os.environ.update(
    {
        "PATH_STORAGE": str(STORAGE_ROOT),
        "PATH_LOGS": str(LOGS_ROOT),
        "PATH_TEMPLATES": str(TEMPLATES_ROOT),
        "PATH_CONFERENCE_TEMPLATE": str(CONFERENCE_TEMPLATE_PATH),
        "PATH_MODULE_DOCX_PROCESSING": str(DOCX_PROCESSING_ROOT),
        "PATH_MODULE_TEMA": str(TEMA_ROOT),
        "PATH_MODULE_CONTENT_VALIDATION": str(CONTENT_VALIDATION_ROOT),
        "CONTENT_VALIDATION_API_URL": CONTENT_VALIDATION_API_URL,
        "PATH_MODULE_SYSTEM": str(BASE_DIR),
    }
)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-conference-system-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "1").strip().lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts.apps.AccountsConfig",
    "submissions.apps.SubmissionsConfig",
    "tema.editorial.apps.EditorialConfig",
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

ROOT_URLCONF = "conference_project.urls"

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
                "accounts.context_processors.role_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "conference_project.wsgi.application"
ASGI_APPLICATION = "conference_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": STORAGE_ROOT / "conference.db",
    }
}

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = STORAGE_ROOT
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CONFERENCE_DEFAULT_ID = "ai_quarterly_conf"
ISSUE_DEFAULT_ID = "2026_q1"
ORGANIZATIONS_SEED_PATH = BASE_DIR / "samples" / "organizations.txt"


LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "").strip()
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
