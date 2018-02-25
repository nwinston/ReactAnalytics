from functools import reduce
from collections import defaultdict
import operator
import re

words_to_ignore = [w.lower() for w in ['a', 'the', 'it', 'that', 'and', 'in', 'I', 'have', '']]

def most_used_reacts(message_manager, count=5):
	reacts = message_manager.react_counts
	return _most_used_reacts(reacts, count)

def _most_used_reacts(reacts, count):
	sorted_reacts = sorted(reacts.items(), key=operator.itemgetter(1))[::-1]
	spliced = sorted_reacts[:count]
	return spliced[::-1]

def favorite_reacts_of_all(message_manager, count=5):
	user_reacts = message_manager.user_reacts
	result = {}
	for user in user_reacts:
		result[user] = favorite_reacts_of_user(message_manager, user, count)
	return result

def favorite_reacts_of_user(message_manager, user, count=5):
	user_reacts = message_manager.get_user_reacts(user)
	return _most_used_reacts(user_reacts, count)

def get_top_by_value(data, count=5):
	sorted_data = sorted(data.items(), key=operator.itemgetter(1))
	spliced = sorted_data[:count]
	return spliced[::-1]

# Given a list of message ids, get all the unique words
# in those messages. Parses escaped channels/users
# (i.e. UserID -> display_name)
def get_unique_words(message_manager, msgs, users, channels):
	channel_re = re.compile('(?<=<#)(.*?)(?=>)')
	user_re = re.compile('(?<=<@)(.*?)(?=>)')

	words = defaultdict(lambda: 1)

	for msg_id in msgs:
		msg_text = message_manager.get_message_text(msg_id)
		split_msg = set([w for w in msg_text.split(' ') if w not in words_to_ignore])
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

def react_buzzword(message_manager, react_name, users, channels):
	msgs = [m for m in message_manager.reacts_on_messages if message_manager.reacts_on_messages.has_react(m, react_name)]
	words = get_unique_words(message_manager, msgs, users, channels)
	ret = get_top_by_value(words)
	return ret

def reacts_to_words(message_manager, users, channels, count=5):

	word_count = {}

	channel_re = re.compile('(?<=<#)(.*?)(?=>)')
	user_re = re.compile('(?<=<@)(.*?)(?=>)')

	word_to_reacts = {}

	for msg_id in message_manager.messages:
		msg_text = message_manager.get_message_text(msg_id)
		split_msg = set(msg_text.split(' '))
		reacts_on_msg = message_manager.get_reacts_on_message(msg_id)
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

def most_reacted_to_posts(message_manager, user_id=None, count=5):
	if user_id:
		ids = message_manager.get_user_message_ids(user_id)
		print(ids)
		reacts_on_messages = {msg : message_manager.reacts_on_messages[msg] for msg in ids if msg in message_manager.reacts_on_messages}
	else:
		reacts_on_messages = message_manager.reacts_on_messages

	react_count = {}
	print(reacts_on_messages)
	for msg_id in reacts_on_messages:
		react_count[msg_id] = reduce((lambda x,y: x + y), reacts_on_messages[msg_id].values())

	return _most_used_reacts(react_count, count)

def most_unique_reacts_on_a_post(message_manager, channel_id=None, count=5):
	msgs = message_manager.get_message_ids(channel_id)
	react_count = {msg : len(message_manager.get_reacts_on_message(msg).keys()) for msg in msgs}
	return _most_used_reacts(react_count, count)



# most reacts on a post
# most single reacts on a post
class ReactCounter:
	def __init__(self):
		self.counter = {} # {'word' : {'react' : count} }
		self.words = {} # {'word' : occurrences_in_different_messages}

	def __str__(self):
		return str(self.counter)

	def add(self, word, reacts):
		if word not in self.words:
			self.words[word] = 1
		else:
			self.words[word] += 1

		for react in reacts:
			self._add(word, react, reacts[react])

	def _add(self, word, react, amt):
		if word in self.counter:
			if react in self.counter[word]:
				count = self.counter[word][react]
				self.counter[word][react] = count + amt
			else:
				self.counter[word][react] = amt
		else:
			self.counter[word] = {react : amt}
