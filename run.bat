@echo off
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
uvicorn conference_system.app.main:app --reload
