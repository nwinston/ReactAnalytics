def msg_id_string(channel_id, time_stamp):
    return channel_id + time_stamp

class React:
    def __init__(self, team_id, channel_id, time_stamp, user_id, react_name):
        self.team_id = team_id
        self.msg_id = msg_id_string(channel_id,time_stamp)
        self.user_id = user_id
        self.react_name = react_name

class Message:
    def __init__(self, team_id, channel_id, time_stamp, user_id, text):
        self.team_id = team_id
        self.msg_id = msg_id_string(channel_id, time_stamp)
        self.user_id = user_id
        self.text = text


