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


class MessageManager(object):
    def __init__(self, messages=None):  # dict of channel to json_msg
        self.messages = {}  # MessageID : 'text'
        self.reacts_on_messages = MessageReacts()  # MessageID : Reacts
        self.user_reacts = UserReacts()
        self.user_messages = {}  # user_id : MessageID
        self.react_counts = {}
        if messages:
            self._on_init(messages)

    def add_message(self, channel_id, time_stamp, user_id, text):
        msg_id = MessageID(channel_id, time_stamp)
        self.messages[msg_id] = text

        if user_id not in self.user_messages:
            self.user_messages[user_id] = [msg_id]
        else:
            self.user_messages[user_id].append(msg_id)

    def add_message_with_reacts(self, channel_id, time_stamp, msg_user, text, reacts):
        self.add_message(channel_id, time_stamp, msg_user, text)
        for react in reacts:
            name = react['name']
            for user in react['users']:
                self.add_react(channel_id, time_stamp, user, name)

    def add_react(self, channel_id, time_stamp, user_id, react_name):
        msg_id = MessageID(channel_id, time_stamp)
        self.reacts_on_messages.add_react(msg_id, react_name)
        self.user_reacts.add_react(user_id, react_name)
        if react_name not in self.react_counts:
            self.react_counts[react_name] = 1
        else:
            self.react_counts[react_name] += 1

    def remove_react(self, channel_id, time_stamp, user_id, react_name):
        msg_id = MessageID(channel_id, time_stamp)
        self.reacts_on_messages.remove_react(msg_id, react_name)
        self.user_reacts.remove_react(user_id, react_name)
        if react_name not in self.react_counts:
            raise Exception('React not in react_counts')
        else:
            if self.react_counts[react_name] <= 1:
                self.react_counts[react_name] = 0
            else:
                self.react_counts[react_name] -= 1

    def get_user_messages(self, user_id):
        msg_ids = self.get_user_message_ids(user_id)
        return [self.messages[msg_id] for msg_id in msg_ids]

    def get_message_ids(self, channel_id=None):
        if channel_id:
            return [msg_id for msg_id in self.messages if msg_id.channel_id == channel_id]
        else:
            return self.messages.keys()

    def get_message_text(self, msg_id):
        return self.messages.get(msg_id, None)

    def get_reacts_on_message(self, msg_id):
        return self.reacts_on_messages.get(msg_id, {})

    def get_user_reacts(self, user_id):
        return self.user_reacts.get(user_id, {})

    def get_user_message_ids(self, user_id):
        return self.user_messages.get(user_id, {})

    def get_reacts_on_user(self, user_id):
        msgs = self.user_messages[user_id]
        reacts = {}
        for msg_id in msgs:
            msg_reacts = self.reacts_on_messages[msg_id]
            for r in msg_reacts:
                if r in reacts:
                    reacts[r] += msg_reacts[r]
                else:
                    reacts[r] = msg_reacts[r]
        return reacts

    def _on_init(self, messages):
        for channel_id in messages:
            for msg in messages[channel_id]:
                time_stamp = msg['ts']
                user_id = msg['user']
                text = msg['text']
                if 'reactions' in msg:
                    reacts = msg['reactions']
                    self.add_message_with_reacts(channel_id, time_stamp, user_id, text, reacts)
                else:
                    self.add_message(channel_id, time_stamp, user_id, text)


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
