web: gunicorn --chdir src app:app
worker: celery --workdir src -A app worker --loglevel=info