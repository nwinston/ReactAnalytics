web: gunicorn --chdir src app:app
worker: celery --workdir src -A app.celery worker --loglevel=DEBUG