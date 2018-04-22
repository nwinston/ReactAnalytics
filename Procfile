web: gunicorn --chdir src app:app
worker: celery -A tasks worker --loglevel=info