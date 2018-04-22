from flask import Flask, request, make_response, render_template, abort
from bot import VALID_COMMANDS, EVENT_TYPE_SLASH_COMMAND, EVENT_TYPE_API_EVENT, Bot
import log
from celery import Celery
import os

app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379')
app.config['CELERY_RESULT_BACKEND'] = os.getenv('REDIS_URL', 'redis://localhost:6379')

def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

pyBot = Bot()
celery = make_celery(app)


@celery.task
def queue_bot_event(token, event_type, event):
    print('queue_bot_event')
    if pyBot.verify_token(token):
        pyBot.on_event(event_type, event)
        return True
    else:
        return False




@app.route("/install", methods=['GET'])
def pre_install():
    client_id = bot.Bot.oauth['client_id']
    scope = ['channels:read', 'channels:history', 'reactions:read', 'team:read']
    return render_template('install.html', client_id=client_id, scope=scope)


@app.route('/thanks', methods=['GET', 'POST'])
def thanks():
    print('thanks')
    #code_arg = request.args.get('code')
    #pyBot.auth(code_arg)
    return render_template('thanks.html')


@app.route('/listening', methods=['GET', 'POST'])
def hears():
    slack_event = request.get_json()

    if 'challenge' in slack_event:
        return make_response(slack_event['challenge'], 200, {
            'content_type': 'application/json'
        })

    if 'event' in slack_event:
        task = queue_bot_event.delay(slack_event.get('token'), EVENT_TYPE_API_EVENT, slack_event)
        if not task:
            message = "Invalid Slack verification token"
            # By adding "X-Slack-No-Retry" : 1 to our response headers, we turn off
            # Slack's automatic retries during development.
            return make_response(message, 403, {"X-Slack-No-Retry": 1})

    return make_response('Non-reaction event', 200)


def get_help_response():
    formatted_resp = ['%s %s\n' % (cmd, arg_list) for cmd, arg_list in VALID_COMMANDS.items()]
    return formatted_resp

@app.route('/react_analytics', methods=['GET', 'POST'])
def on_slash_command():
    print('slash_command')
    slash_command = parse_slash_command(request)
    text = slash_command['text']
    response_text = 'use [/reacts help] for options'
    if text.lower().strip() == 'help':
        return make_response(get_help_response(), 200)
    if text.split(' ')[0] in VALID_COMMANDS:
        task = queue_bot_event.delay(slash_command['token'], EVENT_TYPE_SLASH_COMMAND, slash_command)
        if not task:
            response_text = 'Invalid token'
        else:
            response_text = ''
    return make_response(response_text, 200)



def parse_slash_command(request):
    result = {'token': request.form.get('token', None),
              'command': request.form.get('command', None),
              'text': request.form.get('text', None),
              'user_id': request.form.get('user_id')}

    if not result['token']:
        abort(400)

    return result


if __name__ == '__main__':
    log.log_info('Starting app')
    app.run(debug=True)
