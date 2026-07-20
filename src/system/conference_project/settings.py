from pathlib import Path
import os
import sys

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


# conference-system/src/system
BASE_DIR = Path(__file__).resolve().parent.parent
# conference-system/src
SRC_ROOT = BASE_DIR.parent
# conference-system
PROJECT_ROOT = SRC_ROOT.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Главный модуль загружает общий .env всего репозитория. Переменные,
# уже заданные операционной системой/CI, имеют приоритет.
load_dotenv(ENV_FILE, override=False)


def _first_env(*names: str) -> str:
    """Return the first non-empty environment value from the supplied names."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def resolve_project_path(*variable_names: str, default: Path) -> Path:
    """Resolve a configured path relative to the repository root."""
    raw_value = _first_env(*variable_names)
    path = Path(raw_value) if raw_value else Path(default)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


# Модуль студента 2. Поддерживаем также старое имя переменной с опечаткой,
# чтобы локальные .env участников команды не перестали работать внезапно.
DOCX_PROCESSING_ROOT = resolve_project_path(
    "PATH_MODULE_DOCX_PROCESSING",
    "PATH_MODULE_DOCX_PROCESSONG",
    "DOCX_PROCESSING_ROOT",
    default=SRC_ROOT / "docx_processing",
)

if not (DOCX_PROCESSING_ROOT / "__init__.py").exists():
    raise ImproperlyConfigured(
        "Не найден модуль docx_processing. Проверьте PATH_MODULE_DOCX_PROCESSING "
        f"в {ENV_FILE}. Текущий путь: {DOCX_PROCESSING_ROOT}"
    )

# Для импорта `docx_processing.*` Python должен видеть родительскую папку модуля.
docx_processing_parent = str(DOCX_PROCESSING_ROOT.parent)
if docx_processing_parent not in sys.path:
    sys.path.insert(0, docx_processing_parent)

STORAGE_ROOT = resolve_project_path(
    "PATH_STORAGE",
    "STORAGE_ROOT",
    default=PROJECT_ROOT / "storage",
)

LOGS_ROOT = resolve_project_path(
    "PATH_LOGS",
    default=STORAGE_ROOT / "logs",
)

TEMPLATES_ROOT = resolve_project_path(
    "PATH_TEMPLATES",
    default=PROJECT_ROOT / "templates",
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

STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
LOGS_ROOT.mkdir(parents=True, exist_ok=True)
SUBMISSIONS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# После чтения .env публикуем уже нормализованные абсолютные пути в среде
# главного процесса. Импортируемый DOCX-модуль и любые дочерние процессы
# получают одинаковые значения независимо от текущей рабочей директории.
os.environ.update(
    {
        "PATH_STORAGE": str(STORAGE_ROOT),
        "PATH_LOGS": str(LOGS_ROOT),
        "PATH_TEMPLATES": str(TEMPLATES_ROOT),
        "PATH_CONFERENCE_TEMPLATE": str(CONFERENCE_TEMPLATE_PATH),
        "PATH_MODULE_DOCX_PROCESSING": str(DOCX_PROCESSING_ROOT),
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
    "submissions.apps.SubmissionsConfig",
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
