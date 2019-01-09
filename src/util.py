def msg_id_string(channel_id, time_stamp):
    return channel_id + time_stamp

def create_react(slack_event):
    event = slack_event['event']
    react_name = event['reaction']
    user_id = event['user']
    channel_id = event['item']['channel']
    time_stamp = event['item']['ts']
    return React('', channel_id, time_stamp, user_id, react_name)

def create_message(slack_event):
    event = slack_event['event']
    channel_id = event['channel']
    user_id = event['user']
    time_stamp = event['ts']
    text = event['text']
    return Message('', channel_id, time_stamp, user_id, text)

class React:
    def __init__(self, team_id, channel_id, time_stamp, user_id, name):
        self.team_id = team_id
        self.msg_id = msg_id_string(channel_id,time_stamp)
        self.user_id = user_id
        self.name = name

class Message:
    def __init__(self, team_id, channel_id, time_stamp, user_id, text):
        self.team_id = team_id
        self.msg_id = msg_id_string(channel_id, time_stamp)
        self.user_id = user_id
        self.text = text

def time_it(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        import time
        start = time.time()
        ret_val = func(*args, **kwargs)
        end = time.time()
        duration = end - start
        print('Time elapsed for ' + str(func.__name__) + ' : ' + str(duration) + ' seconds')
        return ret_val
    return wrapper