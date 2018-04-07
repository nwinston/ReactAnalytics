import db

class MessageID(object):
    def __init__(self, channel_id, time_stamp):
        self.channel_id = channel_id
        self.time_stamp = time_stamp

    def __hash__(self):
        return hash((self.channel_id, self.time_stamp))

    def __eq__(self, other):
        return self.channel_id == other.channel_id and self.time_stamp == other.time_stamp

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return 'channel_id: ' + str(self.channel_id) + ' time_stamp: ' + str(self.time_stamp)


def msg_id_string(channel_id, time_stamp):
    return channel_id + time_stamp

class MessageDBAdapter(object):

    def add_message(self, team_id, channel_id, time_stamp, user_id, text):
        msg_id = msg_id_string(channel_id, time_stamp)
        db.add_message((msg_id, team_id, user_id, text))

    def add_messages(self, msgs):
        msgs = [(msg_id_string(msg[1], msg[2]), msg[0], msg[3], msg[4]) for msg in msgs]
        db.add_messages(msgs)

    def remove_message(self, channel_id, time_stamp):
        msg_id = msg_id_string(channel_id, time_stamp)

    def add_reacts(self, reacts):
        reacts = [(msg_id_string(react[1], react[2]), react[0], react[3], react[4]) for react in reacts]
        db.add_reacts(reacts)


    def add_react(self, team_id, channel_id, time_stamp, user_id, react_name):
        msg_id = msg_id_string(channel_id, time_stamp)
        msgs = (msg_id, team_id, user_id, react_name)
        db.add_reacts([msgs])

    def remove_react(self, team_id, channel_id, time_stamp, user_id, react_name):
        msg_id = msg_id_string(channel_id, time_stamp)
        db.remove_react(msg_id, user_id, react_name)

    def get_user_messages(self, team_id, user_id):
        msg_ids = db.get_messages_by_user(team_id, user_id)
        return msg_ids

    def get_message_ids(self, team_id, channel_id=None):
        return db.get_message_ids()

    def get_message_text(self, team_id, msg_id):
        return db.get_message_text(team_id, msg_id)

    def get_all_message_texts(self, team_id):
        return db.get_all_message_texts()

    def get_reacts_on_message(self, msg_id):
        return db.get_reacts_on_message(msg_id)

    def get_user_reacts(self, team_id, user_id):
        return db.get_reacts_by_user(user_id)

    def get_user_message_ids(self, team_id, user_id):
        return db.get_messages_by_user(user_id)

    def get_reacts_on_user(self, team_id, user_id):
        return db.get_reacts_on_user(user_id)

    def add_auth_team(self, code, bot_access_code):
        db.add_auth_team(code, bot_access_code)

    def get_bot_token(self, team_id):
        return db.get_bot_token(team_id)

    def msg_in_db(self, team_id, channel_id, ts):
        return db.msg_exists(msg_id_string(channel_id, ts))


class MessageReacts(object):
    def __init__(self):
        self.reacts = {}  # {MessageID : {'react_name' : count}}

    def __contains__(self, key):
        return key in self.reacts

    def __getitem__(self, key):
        return self.reacts[key]

    def __setitem__(self, key, value):
        self.reacts[key] = value

    def __iter__(self):
        return iter(self.reacts)

    def add_react(self, msg_id, react_name):
        if msg_id not in self.reacts:
            self.reacts[msg_id] = {react_name: 1}
            return
        if react_name not in self.reacts[msg_id]:
            self.reacts[msg_id][react_name] = 1
            return
        self.reacts[msg_id][react_name] += 1

    def remove_react(self, msg_id, react_name):
        if msg_id not in self.reacts:
            return
        if react_name not in self.reacts[msg_id]:
            return
        if self.reacts[msg_id][react_name] <= 1:
            self.reacts[msg_id][react_name] = 0

    def get(self, key, default):
        return self.reacts.get(key, default)

    def keys(self):
        return self.reacts.keys()

    def has_react(self, msg_id, react_name):
        if msg_id not in self.reacts:
            return False
        return react_name in self.reacts[msg_id]


class UserReacts(object):
    def __init__(self):
        self.reacts = {}  # {'user_id' : {'react_name' : count}}

    def __contains__(self, key):
        return key in self.reacts

    def __getitem__(self, key):
        return self.reacts[key]

    def __setitem__(self, key, value):
        self.reacts[key] = value

    def __iter__(self):
        return iter(self.reacts)

    def add_react(self, user_id, react_name):
        # should short circuit if user doesn't exist and will create
        # the new entry regardless
        if user_id not in self.reacts:
            self.reacts[user_id] = {react_name: 1}
            return
        if react_name not in self.reacts[user_id]:
            self.reacts[user_id][react_name] = 1
            return
        self.reacts[user_id][react_name] += 1

    def remove_react(self, user_id, react_name):
        if user_id not in self.reacts:
            return
        if react_name not in self.reacts[user_id]:
            return
        if self.reacts[user_id][react_name] <= 1:
            self.reacts[user_id][react_name] = 0

    def get(self, key, default):
        return self.reacts.get(key, default)
