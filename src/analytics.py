from functools import reduce
from collections import defaultdict, OrderedDict, Counter
import operator
import re
import db
import os
from nltk.util import ngrams
from nltk import word_tokenize, sent_tokenize, TweetTokenizer #doesn't split contractions
import string
from contractions import expand_contractions

up_dir = os.path.dirname(os.path.dirname(__file__))
stop_words_file = up_dir + '/stopwords.txt'
stop_words = set(line.strip() for line in open(stop_words_file))
stop_words.add('')

punc = string.punctuation
punc += '”'
punc += '“'

#nltk.download()

omit_phrases = ['joined the channel', 'left the channel', 'pinned a message', 'uploaded a file']

def most_used_reacts(count=5):
	reacts = db.get_react_counts()
	return _most_used_reacts(reacts, count)

def _most_used_reacts(reacts, count):
	sorted_reacts = sorted(reacts.items(), key=operator.itemgetter(1))[::-1]
	spliced = sorted_reacts[:count]
	return spliced[::-1]

def favorite_reacts_of_all(users, count=5):
	user_reacts = {user : db.get_reacts_by_user(user) for user in users}
	result = {}
	for user in user_reacts:
		result[user] = favorite_reacts_of_user(user, count)
	return result

def favorite_reacts_of_user(user, count=5):
	user_reacts = db.get_reacts_by_user(user)
	return _most_used_reacts(user_reacts, count)

def get_top_by_value(data, count=5, sort_key=operator.itemgetter(1)):
	sorted_data = sorted(data.items(), key=sort_key)[::-1]
	if count > 0:
		sorted_data = sorted_data[:count]
	return {item[0] : item[1] for item in sorted_data}

# Given a list of message ids, get all the unique words
# in those messages. Parses escaped channels/users
# (i.e. UserID -> display_name)
def get_unique_words( msgs, users, channels):
	channel_re = re.compile('(?<=<#)(.*?)(?=>)')
	user_re = re.compile('(?<=<@)(.*?)(?=>)')

	words = defaultdict(lambda: 1)

	translator = str.maketrans('', '', punc)

	msgs = db.get_message_text_from_ids(msgs)

	for msg_id in msgs:
		msg_text = msgs[msg_id].lower()
		if not msg_text:
			continue
		#msg_text.translate(translator)
		split_msg = {w.translate(translator) for w in msg_text.split(' ') if w.lower() not in stop_words}
		print(split_msg)
		for word in split_msg:
			# tmp variable in case word is escaped (i.e linked name/channel)
			key = word

			ch_find = channel_re.search(word)
			if ch_find:
				ch_id = ch_find.group(0)
				if ch_id in channels:
					key = channels[ch_id]
			user_find = user_re.search(word)
			if user_find:
				user_id = user_find.group(0)
				if user_id in users:
					key = users[user_id]['display_name']
			words[key] += 1
	return dict(words)

def react_buzzword(react_name, users, channels, count=5):
	msgs = db.get_messages_with_react(react_name, False)
	words = get_unique_words(msgs, users, channels)
	ret = get_top_by_value(words, count)
	return ret

def reacts_to_words(users, channels, count=5):

	word_count = {}

	channel_re = re.compile('(?<=<#)(.*?)(?=>)')
	user_re = re.compile('(?<=<@)(.*?)(?=>)')

	word_to_reacts = {}

	for msg_id in db.get_message_ids():
		msg_text = db.get_message_text(msg_id)
		split_msg = set(msg_text.split(' '))
		reacts_on_msg = db.get_reacts_on_message(msg_id)
		if not reacts_on_msg:
			continue
		for w in split_msg:
			key = w

			# If theres a channel ID, get the name
			ch_find = channel_re.search(w)
			if ch_find:
				ch_id = ch_find.group(0)
				if ch_id in channels:
					key = channels[ch_id]

			# If there's a user ID, get the name
			user_find = user_re.search(w)
			if user_find:
				user_id = user_find.group(0)
				if user_id in users:
					key = users[user_id]['display_name']

			if key in word_count:
				word_count[key] += 1
			else:
				word_count[key] = 1

			if key not in word_to_reacts:
				word_to_reacts[key] = {}

			for react in reacts_on_msg:
				if react in word_to_reacts[key]:
					word_to_reacts[key][react] += 1
				else:
					word_to_reacts[key][react] = 1

	return word_to_reacts

def most_reacted_to_posts(user_id=None, count=5):
	if user_id:
		ids = db.get_messages_by_user(user_id)
		print(ids)
		reacts_on_messages = {msg : db.get_reacts_on_message(msg) for msg in ids}
	else:
		reacts_on_messages = db.get_reacts_on_all_messages()

	react_count = {}
	print(reacts_on_messages)
	for msg_id in reacts_on_messages:
		count = 0
		for r in reacts_on_messages[msg_id]:
			count += reacts_on_messages[msg_id][r]
		react_count[msg_id] = count

	return _most_used_reacts(react_count, count)

def get_common_phrases():
	phrase_counter = Counter()
	texts = db.get_all_message_texts()
	for msg in texts:
		if any(omit in msg for omit in omit_phrases):
			continue
		words = msg.split(' ')
		for phrase in ngrams(words, 3):
			if all(word not in string.punctuation for word in phrase):
				phrase_counter[phrase] += 1
	return phrase_counter.most_common(10)

def most_unique_reacts_on_a_post(count=5):
	reacts = db.get_reacts_on_all_messages() # msg_id : {react_name : count}
	reacts = {msg_id : reacts[msg_id] for msg_id in reacts}
	top_by_val = get_top_by_value(reacts, count, lambda x: len(x[1]))
	print(top_by_val)
	return top_by_val

def users_with_most_reacts(count=5):
	most_reacts = Counter(db.get_reacts_per_user())
	print(most_reacts)
	if count < 1:
		count = None
	return Counter(dict(most_reacts.most_common(count)))

def most_messages(count=5):
	msgs = db.get_message_table()
	counter = Counter()
	for msg in msgs:
		counter[msg[2]] += 1
	if count < 1:
		count = None
	return Counter(dict(counter.most_common(count)))

def most_active(count=5):
	most_msgs = most_messages(-1)
	most_reacts = users_with_most_reacts(-1)
	most_active = most_reacts + most_msgs
	return dict(most_active.most_common(count))