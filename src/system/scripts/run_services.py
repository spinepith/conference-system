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
API_PROJECT = PROJECT_ROOT / "src" / "content-validation" / "ContentValidation.Api" / "ContentValidation.Api.csproj"
LOG_PATH = PROJECT_ROOT / "storage" / "logs" / "content_validation_api.log"


def env_enabled(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def health_url() -> str:
    return os.getenv("CONTENT_VALIDATION_API_URL", "http://127.0.0.1:5100").rstrip("/") + "/health"


def service_is_ready() -> bool:
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


def validate_configuration() -> None:
    if not API_PROJECT.is_file():
        raise RuntimeError(f"Проект ContentValidation.Api не найден: {API_PROJECT}")
    if shutil.which("dotnet") is None:
        raise RuntimeError("Команда dotnet не найдена. Установите .NET 10 SDK и перезапустите терминал.")

    sdk_result = subprocess.run(
        ["dotnet", "--list-sdks"],
        capture_output=True,
        text=True,
        check=False,
    )
    if sdk_result.returncode != 0 or not any(
        line.lstrip().startswith("10.") for line in sdk_result.stdout.splitlines()
    ):
        raise RuntimeError("ContentValidation требует установленный .NET 10 SDK.")

    if not os.getenv("API_KEY", "").strip():
        raise RuntimeError(
            f"В {ENV_FILE} не заполнен API_KEY для Gemini. "
            "Укажите ключ либо временно установите CONTENT_VALIDATION_ENABLED=0."
        )
    storage_value = os.getenv("PATH_STORAGE", "").strip()
    if not storage_value:
        raise RuntimeError(f"В {ENV_FILE} не задан PATH_STORAGE=storage.")


def start_content_validation() -> tuple[subprocess.Popen | None, object | None]:
    if service_is_ready():
        print("[ContentValidation] Уже запущен на порту 5100.")
        return None, None

    validate_configuration()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_file = LOG_PATH.open("a", encoding="utf-8")
    log_file.write("\n\n=== ContentValidation.Api startup ===\n")
    log_file.flush()

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        [
            "dotnet",
            "run",
            "--project",
            str(API_PROJECT),
            "--configuration",
            "Release",
            "--no-launch-profile",
        ],
        cwd=PROJECT_ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_file.flush()
            log_file.close()
            raise RuntimeError(
                f"ContentValidation.Api завершился с кодом {process.returncode}. "
                f"Подробности: {LOG_PATH}"
            )
        if service_is_ready():
            print("[ContentValidation] Сервис готов: http://127.0.0.1:5100")
            return process, log_file
        time.sleep(0.5)

    stop_process(process)
    log_file.close()
    raise RuntimeError(f"ContentValidation.Api не запустился за отведённое время. Лог: {LOG_PATH}")


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    print("[ContentValidation] Остановка сервиса...")
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    load_dotenv(ENV_FILE, override=False)
    api_process: subprocess.Popen | None = None
    log_file = None
    try:
        if env_enabled("CONTENT_VALIDATION_ENABLED"):
            api_process, log_file = start_content_validation()
        else:
            print("[ContentValidation] Отключён через CONTENT_VALIDATION_ENABLED=0.")

        print("[Django] Сервер: http://127.0.0.1:8000/")
        return subprocess.call(
            [sys.executable, "manage.py", "runserver", "127.0.0.1:8000"],
            cwd=SYSTEM_DIR,
        )
    except KeyboardInterrupt:
        return 0
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        stop_process(api_process)
        if log_file is not None:
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
