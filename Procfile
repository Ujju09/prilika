web: gunicorn ruralaccounting.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class gthread --log-file - --access-logfile - --error-logfile -
release: python3 manage.py migrate --noinput && python3 manage.py collectstatic --noinput
