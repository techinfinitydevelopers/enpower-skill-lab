web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn enpower_skill_lab.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 60
