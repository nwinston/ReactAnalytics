from flask import Flask, request, make_response, render_template, abort
import bot
import logging

logging.basicConfig(level=logging.WARNING)

app = Flask(__name__)
pyBot = bot.Bot()



@app.route("/install", methods=['GET'])
def pre_install():
    client_id = slack.oauth['client_id']
    scope = ['channels:read', 'channels:history', 'reactions:read', 'team:read']
    return render_template('install.html', client_id=client_id, scope=scope)


@app.route('/thanks', methods=['GET', 'POST'])
def thanks():
    print('thanks')
    code_arg = request.args.get('code')
    pyBot.auth(code_arg)
    return render_template('thanks.html')


@app.route('/listening', methods=['GET', 'POST'])
def hears():
    slack_event = request.get_json()

    if 'challenge' in slack_event:
        return make_response(slack_event['challenge'], 200, {
            'content_type': 'application/json'
        })

    if 'event' in slack_event:
        pyBot.on_event(bot.EventType.API_EVENT, slack_event)

    return make_response('Non-reaction event', 200)

'''
@app.route(bot.MOST_USED_REACTS, methods=['GET', 'POST'])
def most_used_reacts():
    pyBot.on_event(bot.EventType.SLASH_COMMAND, parse_slash_command(request))
    return make_response('', 200)



@app.route(bot.MOST_REACTED_TO_MESSAGES, methods=['GET', 'POST'])
def most_reacted_to_messages():
    pyBot.on_event(bot.EventType.SLASH_COMMAND, parse_slash_command(request))
    return make_response('', 200)

@app.route(bot.MOST_UNIQUE_REACTS_ON_POST, methods=['GET', 'POST'])
def most_unique_reacts_on_post():
    pyBot.on_event(bot.EventType.SLASH_COMMAND, parse_slash_command(request))
    return make_response('', 200)

@app.route(bot.REACTS_TO_WORDS, methods=['GET', 'POST'])
def reacts_to_words():
    pyBot.on_event(bot.EventType.SLASH_COMMAND, parse_slash_command(request))
    return make_response('', 200)
'''
@app.route('/react_analytics', methods=['GET', 'POST'])
def slash_command():
    slash_command = parse_slash_command(request)
    text = slash_command['text']
    response_text = 'use [/react_analytics help] for options'
    if text.lower() == 'help':
        return make_response('try this', 200)
    if text.split(' ')[0] in bot.VALID_COMMANDS:
        pyBot.on_event(bot.EventType.SLASH_COMMAND, slash_command)
        response_text = ''
    return make_response(response_text, 200)



def parse_slash_command(request):
    result = {}

    result['token'] = request.form.get('token', None)
    result['command'] = request.form.get('command', None)
    result['text'] = request.form.get('text', None)
    result['user_id'] = request.form.get('user_id')

    if not result['token']:
        abort(400)

    return result


if __name__ == '__main__':
    app.run(debug=True)
