web: gunicorn --chdir src app:app
worker: celery --workdir src -A tasks worker --loglevel=info