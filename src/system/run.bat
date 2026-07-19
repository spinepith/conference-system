@echo off
python manage.py migrate
python manage.py seed_initial_data
python manage.py runserver
