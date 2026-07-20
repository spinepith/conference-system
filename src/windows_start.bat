@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "SRC_DIR=%~dp0"
for %%I in ("%SRC_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "SYSTEM_DIR=%SRC_DIR%system"
set "ENV_FILE=%PROJECT_ROOT%\.env"
set "ENV_EXAMPLE=%PROJECT_ROOT%\.env.example"
set "VENV_DIR=%PROJECT_ROOT%\.venv"

if not exist "%ENV_EXAMPLE%" (
    echo [ОШИБКА] Не найден файл %ENV_EXAMPLE%
    goto :fail
)

if not exist "%ENV_FILE%" (
    echo [1/6] Создаю корневой .env из .env.example...
    copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
)

if not exist "%SYSTEM_DIR%\manage.py" (
    echo [ОШИБКА] Не найден Django-модуль: %SYSTEM_DIR%\manage.py
    goto :fail
)

if not exist "%PROJECT_ROOT%\templates\conference_template_v1.docx" (
    echo [ОШИБКА] Не найден шаблон conference_template_v1.docx в папке templates.
    goto :fail
)

if not exist "%PROJECT_ROOT%\src\docx_processing\__init__.py" (
    echo [ОШИБКА] Не найден модуль src\docx_processing.
    goto :fail
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [2/6] Создаю виртуальное окружение .venv...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv "%VENV_DIR%"
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo [ОШИБКА] Python не найден. Установите Python 3.11 или новее.
            goto :fail
        )
        python -m venv "%VENV_DIR%"
    )
    if errorlevel 1 goto :fail
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 goto :fail

cd /d "%SYSTEM_DIR%"

echo [3/6] Устанавливаю зависимости...
python -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

echo [4/6] Применяю миграции...
python manage.py migrate
if errorlevel 1 goto :fail

echo [5/6] Создаю начальные данные и проверяю конфигурацию...
python manage.py seed_initial_data
if errorlevel 1 goto :fail
python manage.py check
if errorlevel 1 goto :fail

echo [6/6] Запускаю сервер: http://127.0.0.1:8000/
echo Для остановки нажмите Ctrl+C.
python manage.py runserver 127.0.0.1:8000
exit /b %errorlevel%

:fail
echo.
echo Запуск остановлен из-за ошибки.
pause
exit /b 1
