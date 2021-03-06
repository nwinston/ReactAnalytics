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



# DB Queries
ALL_MESSAGE_TEXTS = 'SELECT Text FROM Messages'
MESSAGES_WITH_REACT = '''
    SELECT Text FROM Messages
    INNER JOIN Reacts ON Messages.MessageID=Reacts.MessageID
    WHERE Reacts.ReactName = %s
    '''
REACTS_BY_USER = '''
    SELECT * FROM Reacts WHERE Reacts.UserID = %s
    '''
ALL_REACTS = '''
    SELECT Messages.MessageID, Text, ReactName FROM Messages
    INNER JOIN Reacts ON Messages.MessageID=Reacts.MessageID
    '''
MOST_REACTED_TO = '''
    SELECT Messages.Text, Count(Reacts.ReactName) FROM Messages
    INNER JOIN Reacts ON Messages.MessageID=Reacts.MessageID
    GROUP BY Messages.MessageID
    ORDER BY Count(Reacts.ReactName) DESC
    '''

REACT_TOTALS = '''SELECT UserID, COUNT(UserID) FROM Reacts 
    GROUP BY UserID
    ORDER BY COUNT(UserID)
    '''

ACTIVITY_TOTALS = '''
    Select UserID, Count(UserID) FROM
    (SELECT UserID FROM Messages UNION ALL
    SELECT UserID FROM Reacts) 
    As t
    GROUP BY UserID
    ORDER BY Count(UserID) DESC
'''


# Might be going a little overboard with the decorators here

def get_top(f, count=5):
    '''
    Returns the most common elements returned by f
    '''
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        counter = Counter(result)
        return dict(counter.most_common(count))
    return wrapper

def to_dict(f):
    '''
    Converts a list of rows to a dict of the first element in the row to a tuple of the rest
    '''
    def wrapper(*args, **kwargs):
        tbl = f(*args, **kwargs)
        tbl = {row[0] : tuple(row[1:]) for row in tbl if row[0]}
        return tbl
    return wrapper



@get_top
@to_dict
def favorite_reacts_of_user(user):
    tbl = db.execute(REACTS_BY_USER, (user,))
    return tbl

def favorite_reacts_of_users(users):
    return {user: favorite_reacts_of_user(user) for user in users}

@get_top
def most_used_reacts(user=None):
    if user:
        return favorite_reacts_of_user(user)

    tbl = db.execute(ALL_REACTS)

    counter = Counter([r[2] for r in tbl])
    return dict(counter)


def translate_token(token, users, channels):
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


def unique_words(msgs, users, channels):
    ''' 
	Args: 
		msgs     (list) : list of messages
		users    (list) : list of "escaped" Slack users
	    channels (list) : list of "escaped" Slack channels

	Returns: 
		Counter: All unique words used in the given messages
	'''

    disp_names = {user : users[user]['display_name'] for user in users}
    unique_words = Counter()
    translator = str.maketrans('', '', punc)

    msgs = [msg for msg in msgs if msg]
    for msg in msgs:
        msg = msg.lower()

        tokenized = {w.translate(translator) for w in msg.split(
            ' ') if w.lower() not in stop_words}
        for token in tokenized:
            key = translate_token(token, disp_names, channels)
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

    msgs = db.execute(MESSAGES_WITH_REACT, (react_name,))
    msgs = [msg[0] for msg in msgs]
    return unique_words(msgs, users, channels)


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

    msgs = db.execute(MOST_REACTED_TO)
    return msgs[:5]

@get_top
def get_common_phrases():
    phrase_counter = Counter()
    texts = db.execute(ALL_MESSAGE_TEXTS)
    texts = [t[0] for t in texts]
    phrases = []

    for text in texts:
        for phrase in ngrams(text.split(' '), 3):
            if phrase in omit_phrases:
                continue
            if any(word in punc for word in phrase):
                continue

            phrase_counter[phrase] += 1
    return phrase_counter

def most_unique_reacts_on_a_post():
    tbl = db.execute(ALL_REACTS)
    
    reacts = defaultdict(set)
    for r in tbl:
        msg_id = r[0]
        txt = r[1]
        key = (msg_id, txt)

        react = r[2]
        # { (MessageID, Text) : [Reacts...] }
        reacts[key].add(react)

    # Store in a list of tuple of (MessageText, [Reacts...])
    tbl = [(key[1], reacts[key]) for key in reacts if key[1]]
    tbl = sorted(tbl, reverse=True, key=lambda r: len(r[1]))

    return tbl[:5]


def most_active():
    tbl = db.execute(ACTIVITY_TOTALS)
    return tbl[:5]

@get_top
@to_dict
def users_with_most_reacts():
    tbl = db.execute(REACT_TOTALS)
    return tbl
