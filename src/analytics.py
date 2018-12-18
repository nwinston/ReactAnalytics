from itertools import islice
from collections import defaultdict, Counter
import operator
import string
import re
import db
import os
from nltk.util import ngrams

up_dir = os.path.dirname(os.path.dirname(__file__))
stop_words_file = up_dir + '/stopwords.txt'
stop_words = set(line.strip() for line in open(stop_words_file))
stop_words.add('')

punc = string.punctuation
# Not sure what codec these two characters are from
# but they are different than the quotes found in
# string.punctuation and are not being removed
punc += '”'
punc += '“'

# Messages we don't want used in the common_phrases method
# because they're posted by slack
omit_phrases = ['joined the channel', 'left the channel',
                'pinned a message', 'uploaded a file']

CHANNEL_EXPR = re.compile('(?<=<#)(.*?)(?=>)')
USER_EXPR = re.compile('(?<=<@)(.*?)(?=>)')


def get_top(f, count=5):
    def wrapper(*args, **kwargs):
        counter = Counter(f(*args, **kwargs))
        return dict(counter.most_common(count))
    return wrapper


@get_top
def favorite_reacts_of_user(user):
    return Counter(db.get_reacts_by_user(user))

def favorite_reacts_of_users(users):
    return {user: favorite_reacts_of_user(user) for user in users}


def get_top_by_value(data, count=5, sort_key=operator.itemgetter(1)):
    sorted_data = sorted(data.items(), key=sort_key)[::-1]
    if count > 0:
        sorted_data = sorted_data[:count]
    return {item[0]: item[1] for item in sorted_data}


def translate(token, users, channels):
    ''' 
    This function converts escaped tokens to their display names. If token is not 
    escaped, the token is returned

	Args: 
		token    (str)  : word to translate
		users    (list) : List of "escaped" Slack users
    	channels (list) : List of "escaped" Slack channels

	Returns: 
		str: translated word
	'''
    find = CHANNEL_EXPR.search(token)
    if find:
        channel_id = find.group(0)
        return channels.get(channel_id, token)

    find = USER_EXPR.search(token)
    if find:
        user_id = find.group(0)
        return users.get(user_id, token)

    return token


def get_unique_words(msgs, users, channels):
    ''' 
	Args: 
		msgs     (list) : list of message IDs 
		users    (list) : list of "escaped" Slack users
	    channels (list) : list of "escaped" Slack channels

	Returns: 
		Counter: All unique words used in the given messages
	'''

    disp_names = {user : users[user]['display_name'] for user in users}
    unique_words = Counter()
    translator = str.maketrans('', '', punc)
    msgs = db.get_message_text_from_ids(msgs)

    for msg_id in msgs:
        msg_text = msgs[msg_id].lower()

        if not msg_text:
            continue

        tokenized = {w.translate(translator) for w in msg_text.split(
            ' ') if w.lower() not in stop_words}
        for token in tokenized:
            key = translate(token, disp_names, channels)
            unique_words[key] += 1

    return unique_words


@get_top
def react_buzzword(react_name, users, channels):
    ''' 
	Finds the words most used in messages with the given react

	Args: 
		react_name (str)  : Slack react name
		users      (list) : List of "escaped" Slack users
	    channels   (list) : List of "escaped" Slack channels
	    count 	   (int)  : Number of results

	Returns: 
		Counter: The most common words used in messages with the given react
'''

    msgs = db.get_messages_with_react(react_name, False)
    return get_unique_words(msgs, users, channels)


@get_top
def most_reacted_to_posts():
    ''' 
    Gets the messages with the most total reactions

    If a user is given, the search is limited to just messages posted
    by that user. Else, the every message is considered.

	Args: 
        user_id (str) : Slack user ID
        count (list)  : Number of results

	Returns: 
    	Counter: messages with the most reactions
	'''

    query = '''
	        SELECT Messages.MessageText, SUM(MessageReacts.Count) FROM Messages
	        INNER JOIN MessageReacts ON Messages.MessageID=MessageReacts.MessageID
	        GROUP BY Messages.MessageID
	    	'''

    msgs = db.execute(query)
    msgs = {msg[0] : msg[1] for msg in msgs}
    return msgs


@get_top
def get_common_phrases():
    phrase_counter = Counter()
    texts = db.get_all_message_texts()
    for msg in texts:
        if any(omit in msg for omit in omit_phrases):
            continue
        words = msg.split(' ')
        for phrase in ngrams(words, 3):
            if all(word not in punc for word in phrase):
                phrase_counter[phrase] += 1
    return phrase_counter


@get_top
def most_unique_reacts_on_a_post():
    query = '''
			SELECT Messages.MessageText, Count(DISTINCT ReactName), Messages.MessageID FROM Messages
			INNER JOIN MessageReacts ON Messages.MessageID=MessageReacts.MessageID
			'''
    msgs = db.execute(query)
    counts = {msg[0] : msgs[1] for msg in msgs}
    return counts


@get_top
def users_with_most_reacts():
    return db.get_react_usage_totals()
