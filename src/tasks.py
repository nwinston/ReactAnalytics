import celery
from bot import Bot

pyBot = Bot()

@celery.task
def queue_bot_event(token, event_type, event):
    if pyBot.verify_token(token):
        pyBot.on_event(event_type, event)
        return True
    else:
        return False
