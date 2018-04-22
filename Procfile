web: gunicorn --chdir src app:app
worker: celery -A src\tasks worker --loglevel=info