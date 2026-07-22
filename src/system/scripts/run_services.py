from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv


SYSTEM_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SYSTEM_DIR.parents[1]
ENV_FILE = PROJECT_ROOT / ".env"

API_PROJECT = (
    PROJECT_ROOT
    / "src"
    / "content-validation"
    / "ContentValidation.Api"
    / "ContentValidation.Api.csproj"
)

SOURCE_PROMPTS_DIR = (
    PROJECT_ROOT
    / "src"
    / "content-validation"
    / "ContentValidation"
    / "Prompts"
)

DEFAULT_API_URL = "http://127.0.0.1:5100"
DEFAULT_STARTUP_TIMEOUT = 180.0


def env_enabled(name: str, default: str = "1") -> bool:
    """Преобразует переменную окружения в bool."""
    return os.getenv(name, default).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def resolve_path(value: str, *, base: Path = PROJECT_ROOT) -> Path:
    """Преобразует путь из .env в абсолютный путь.

    Относительные пути считаются относительно корня репозитория.
    Поддерживаются переменные окружения и символ ~.
    """
    expanded = os.path.expandvars(value.strip().strip('"')).strip()
    path = Path(expanded).expanduser()

    if not path.is_absolute():
        path = base / path

    return path.resolve()


def api_base_url() -> str:
    return os.getenv(
        "CONTENT_VALIDATION_API_URL",
        DEFAULT_API_URL,
    ).strip().rstrip("/")


def health_url() -> str:
    return f"{api_base_url()}/health"


def service_is_ready() -> bool:
    """Проверяет готовность ContentValidation.Api."""
    try:
        with urlopen(health_url(), timeout=1.0) as response:
            if response.status != 200:
                return False

            payload = json.loads(response.read().decode("utf-8"))
            return (
                payload.get("status") == "ok"
                and payload.get("service") == "ContentValidation.Api"
            )
    except (OSError, URLError, json.JSONDecodeError):
        return False


def content_validation_log_path() -> Path:
    logs_value = os.getenv("PATH_LOGS", "storage/logs").strip()
    logs_dir = resolve_path(logs_value)
    return logs_dir / "content_validation_api.log"


def storage_path() -> Path:
    value = os.getenv("PATH_STORAGE", "").strip()
    if not value:
        raise RuntimeError(
            f"В {ENV_FILE} не задан PATH_STORAGE. "
            "Например: PATH_STORAGE=storage"
        )

    path = resolve_path(value)
    if not path.is_dir():
        raise RuntimeError(f"Папка storage не найдена: {path}")

    return path


def api_executable_path() -> Path | None:
    """Возвращает путь к внешней Windows-сборке, если он указан."""
    value = os.getenv("CONTENT_VALIDATION_EXE_PATH", "").strip()
    if not value:
        return None

    return resolve_path(value)


def startup_timeout() -> float:
    value = os.getenv(
        "CONTENT_VALIDATION_STARTUP_TIMEOUT",
        str(DEFAULT_STARTUP_TIMEOUT),
    ).strip()

    try:
        timeout = float(value)
    except ValueError as exc:
        raise RuntimeError(
            "CONTENT_VALIDATION_STARTUP_TIMEOUT должен быть числом."
        ) from exc

    if timeout <= 0:
        raise RuntimeError(
            "CONTENT_VALIDATION_STARTUP_TIMEOUT должен быть больше нуля."
        )

    return timeout


def validate_common_configuration() -> tuple[Path, str]:
    """Проверяет общие настройки C#-модуля."""
    if not ENV_FILE.is_file():
        raise RuntimeError(f"Файл окружения не найден: {ENV_FILE}")

    if not os.getenv("API_KEY", "").strip():
        raise RuntimeError(
            f"В {ENV_FILE} не заполнен API_KEY для Gemini. "
            "Укажите ключ либо временно установите "
            "CONTENT_VALIDATION_ENABLED=0."
        )

    model = os.getenv(
        "LLM_MODEL",
        "gemini-3.1-flash-lite",
    ).strip()
    if not model:
        raise RuntimeError(f"В {ENV_FILE} не заполнен LLM_MODEL.")

    return storage_path(), model


def build_content_validation_launch() -> tuple[
    list[str],
    Path,
    dict[str, str],
    str,
]:
    """Собирает команду запуска ContentValidation.Api.

    При наличии CONTENT_VALIDATION_EXE_PATH запускается готовый .exe.
    Если путь не задан, используется резервный запуск через dotnet run.
    """
    resolved_storage, model = validate_common_configuration()

    child_env = os.environ.copy()

    # Для внешнего .exe рабочая папка отличается от корня проекта.
    # Поэтому PATH_STORAGE обязательно передаём как абсолютный путь.
    child_env["PATH_STORAGE"] = str(resolved_storage)
    child_env["LLM_MODEL"] = model

    executable = api_executable_path()
    if executable is not None:
        if os.name != "nt":
            raise RuntimeError(
                "CONTENT_VALIDATION_EXE_PATH указывает на Windows .exe, "
                "но проект запущен не в Windows."
            )

        if not executable.is_file():
            raise RuntimeError(
                "ContentValidation.Api.exe не найден: "
                f"{executable}"
            )

        prompts_value = os.getenv(
            "CONTENT_VALIDATION_PROMPTS_PATH",
            "",
        ).strip()
        prompts_dir = (
            resolve_path(prompts_value)
            if prompts_value
            else executable.parent / "Prompts"
        )

        if not prompts_dir.is_dir():
            raise RuntimeError(
                "Папка Prompts для ContentValidation.Api не найдена: "
                f"{prompts_dir}. Распакуйте всю папку win-x64, "
                "а не только ContentValidation.Api.exe."
            )

        command = [
            str(executable),
            "--env",
            str(ENV_FILE),
            "--storage",
            str(resolved_storage),
            "--prompts",
            str(prompts_dir),
            "--model",
            model,
        ]

        return command, executable.parent, child_env, "готовый .exe"

    # Резервный режим для разработчиков, у которых нет готовой сборки.
    if not API_PROJECT.is_file():
        raise RuntimeError(
            "Не задан CONTENT_VALIDATION_EXE_PATH и не найден проект "
            f"ContentValidation.Api: {API_PROJECT}"
        )

    if shutil.which("dotnet") is None:
        raise RuntimeError(
            "Не задан CONTENT_VALIDATION_EXE_PATH и команда dotnet "
            "не найдена. Укажите путь к ContentValidation.Api.exe "
            "либо установите .NET 10 SDK."
        )

    sdk_result = subprocess.run(
        ["dotnet", "--list-sdks"],
        capture_output=True,
        text=True,
        check=False,
    )
    if sdk_result.returncode != 0 or not any(
        line.lstrip().startswith("10.")
        for line in sdk_result.stdout.splitlines()
    ):
        raise RuntimeError(
            "Для резервного запуска через dotnet требуется .NET 10 SDK."
        )

    if not SOURCE_PROMPTS_DIR.is_dir():
        raise RuntimeError(
            f"Папка Prompts не найдена: {SOURCE_PROMPTS_DIR}"
        )

    command = [
        "dotnet",
        "run",
        "--project",
        str(API_PROJECT),
        "--configuration",
        "Release",
        "--no-launch-profile",
        "--",
        "--env",
        str(ENV_FILE),
        "--storage",
        str(resolved_storage),
        "--prompts",
        str(SOURCE_PROMPTS_DIR),
        "--model",
        model,
    ]

    return command, PROJECT_ROOT, child_env, "dotnet run"


def start_content_validation() -> tuple[
    subprocess.Popen | None,
    object | None,
]:
    """Запускает ContentValidation.Api и ждёт готовности /health."""
    if service_is_ready():
        print(
            "[ContentValidation] Уже запущен: "
            f"{api_base_url()}"
        )
        return None, None

    command, working_directory, child_env, launch_mode = (
        build_content_validation_launch()
    )

    log_path = content_validation_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_file = log_path.open("a", encoding="utf-8")
    log_file.write("\n\n=== ContentValidation.Api startup ===\n")
    log_file.write(f"Mode: {launch_mode}\n")
    log_file.write(f"Working directory: {working_directory}\n")
    log_file.write(f"API URL: {api_base_url()}\n")
    log_file.flush()

    creationflags = (
        subprocess.CREATE_NEW_PROCESS_GROUP
        if os.name == "nt"
        else 0
    )

    try:
        process = subprocess.Popen(
            command,
            cwd=str(working_directory),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            env=child_env,
        )
    except OSError:
        log_file.close()
        raise

    print(f"[ContentValidation] Запуск: {launch_mode}")

    deadline = time.monotonic() + startup_timeout()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_file.flush()
            log_file.close()
            raise RuntimeError(
                "ContentValidation.Api завершился с кодом "
                f"{process.returncode}. Подробности: {log_path}"
            )

        if service_is_ready():
            print(
                "[ContentValidation] Сервис готов: "
                f"{api_base_url()}"
            )
            return process, log_file

        time.sleep(0.5)

    stop_process(process)
    log_file.close()
    raise RuntimeError(
        "ContentValidation.Api не запустился за отведённое время. "
        f"Лог: {log_path}"
    )


def stop_process(process: subprocess.Popen | None) -> None:
    """Завершает процесс C#-сервиса вместе с дочерними процессами."""
    if process is None or process.poll() is not None:
        return

    print("[ContentValidation] Остановка сервиса...")

    if os.name == "nt":
        subprocess.run(
            [
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    load_dotenv(ENV_FILE, override=False)

    api_process: subprocess.Popen | None = None
    log_file = None

    try:
        if env_enabled("CONTENT_VALIDATION_ENABLED"):
            api_process, log_file = start_content_validation()
        else:
            print(
                "[ContentValidation] Отключён через "
                "CONTENT_VALIDATION_ENABLED=0."
            )

        print("[Django] Сервер: http://127.0.0.1:8000/")
        return subprocess.call(
            [
                sys.executable,
                "manage.py",
                "runserver",
                "127.0.0.1:8000",
            ],
            cwd=str(SYSTEM_DIR),
            env=os.environ.copy(),
        )
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        stop_process(api_process)
        if log_file is not None and not log_file.closed:
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())