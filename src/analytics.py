from functools import reduce
from collections import defaultdict
import operator
import re
import db
import os
import nltk
from nltk.collocations import *

up_dir = os.path.dirname(os.path.dirname(__file__))
stop_words_file = up_dir + '/stopwords.txt'
stop_words = set(line.strip() for line in open(stop_words_file))
stop_words.add('')

def most_used_reacts(count=5):
	reacts = db.get_react_counts()
	return _most_used_reacts(reacts, count)

def _most_used_reacts(reacts, count):
	print(reacts)
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

def get_top_by_value(data, count=5):
	sorted_data = sorted(data.items(), key=operator.itemgetter(1))
	spliced = sorted_data[:count]
	return {item[0] : item[1] for item in spliced}

# Given a list of message ids, get all the unique words
# in those messages. Parses escaped channels/users
# (i.e. UserID -> display_name)
def get_unique_words( msgs, users, channels):
	channel_re = re.compile('(?<=<#)(.*?)(?=>)')
	user_re = re.compile('(?<=<@)(.*?)(?=>)')

	words = defaultdict(lambda: 1)

	msgs = db.get_message_text_from_ids(msgs)

	for msg_id in msgs:
		msg_text = msgs[msg_id]
		print(msg_id)
		print(msg_text)
		if not msg_text:
			continue
		split_msg = set([w for w in msg_text.split(' ') if w not in stop_words])
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
	print(words)
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

def get_common_phrases(msg_db):
	texts = msg_db.get_all_message_texts()
	bigram_measures = nltk.collocations.BigramAssocMeasures()
	trigram_measures = nltk.collocations.TrigramAssocMeasures()

	finder = BigramCollocationFinder.from_words(texts)
	finder.apply_freq_filter(3)
	return finder.nbest(bigram_measures.pmi, 10)

def most_unique_reacts_on_a_post(count=5):
	react_count = db.get_reacts_on_all_messages() # msg_id : {react_name : count}
	react_count = {msg_id : len(react_count[msg_id]) for msg_id in react_count}
	print(react_count)
	return _most_used_reacts(react_count, count)

def users_with_most_reacts(count=5):
	most_reacts = db.get_reacts_per_user()
	return get_top_by_value(most_reacts, count)

