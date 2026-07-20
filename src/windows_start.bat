@echo off
setlocal EnableExtensions

set "SRC_DIR=%~dp0"
for %%I in ("%SRC_DIR%..") do set "PROJECT_ROOT=%%~fI"

set "SYSTEM_DIR=%SRC_DIR%system"
set "ENV_FILE=%PROJECT_ROOT%\.env"
set "ENV_EXAMPLE=%PROJECT_ROOT%\.env.example"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

echo ==========================================
echo Conference System
echo ==========================================

if not exist "%ENV_EXAMPLE%" (
    echo [ERROR] File not found:
    echo %ENV_EXAMPLE%
    goto :fail
)

if not exist "%ENV_FILE%" (
    echo [1/6] Creating .env from .env.example...
    copy /Y "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
    if errorlevel 1 goto :fail
)

if not exist "%SYSTEM_DIR%\manage.py" (
    echo [ERROR] Django manage.py was not found:
    echo %SYSTEM_DIR%\manage.py
    goto :fail
)

if not exist "%PROJECT_ROOT%\templates\conference_template_v1.docx" (
    echo [ERROR] Conference template was not found:
    echo %PROJECT_ROOT%\templates\conference_template_v1.docx
    goto :fail
)

if not exist "%PROJECT_ROOT%\src\docx_processing\__init__.py" (
    echo [ERROR] DOCX processing module was not found:
    echo %PROJECT_ROOT%\src\docx_processing
    goto :fail
)

if not exist "%PYTHON_EXE%" (
    echo [2/6] Creating virtual environment...

    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv "%VENV_DIR%"
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Python was not found.
            echo Install Python 3.11 or newer and enable Add Python to PATH.
            goto :fail
        )
        python -m venv "%VENV_DIR%"
    )

    if errorlevel 1 goto :fail
)

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment Python was not created:
    echo %PYTHON_EXE%
    goto :fail
)

cd /d "%SYSTEM_DIR%"
if errorlevel 1 goto :fail

echo [3/6] Installing dependencies...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

echo [4/6] Applying database migrations...
"%PYTHON_EXE%" manage.py migrate
if errorlevel 1 goto :fail

echo [5/6] Creating initial data and checking configuration...
"%PYTHON_EXE%" manage.py seed_initial_data
if errorlevel 1 goto :fail

"%PYTHON_EXE%" manage.py check
if errorlevel 1 goto :fail

echo [6/6] Starting server at http://127.0.0.1:8000/
echo Press Ctrl+C to stop the server.
echo.

"%PYTHON_EXE%" manage.py runserver 127.0.0.1:8000
exit /b %errorlevel%

:fail
echo.
echo Startup failed.
pause
exit /b 1
