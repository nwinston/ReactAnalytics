from flask import make_response
import analytics
import re


class EventManager(object):
	def __init__(self, slack, message_manager):
		self.last_message_get = '0'
		self.slack = slack
		self.message_manager = message_manager

	def on_reaction_added(self, slack_event):
		event = slack_event['event']
		react_name = event['reaction']
		user_id = event['user']
		channel_id = event['item']['channel']
		time_stamp = event['item']['ts']
		self.message_manager.add_react(channel_id, time_stamp, user_id, react_name)
		return make_response('Reaction Added', 200)

	def on_reaction_removed(self, slack_event):
		event = slack_event['event']
		react_name = event['reaction']
		user_id = event['user']
		channel_id = event['item']['channel']
		time_stamp = event['item']['ts']
		self.message_manager.remove_react(channel_id, time_stamp, user_id, react_name)
		return make_response('Reaction Removed', 200)

	def on_message(self, slack_event):
		event = slack_event['event']
		channel_id = event['channel']
		user_id = event['user']
		time_stamp = event['ts']
		text = event['text']
		self.message_manager.add_message(channel_id, time_stamp, user_id, text)
		return make_response('Received', 200)

	#def on_slash_command(self, command, text):

	def most_reacted_to_messages(self, text):
		re_object = re.search('(?<=\@)(.*?)(?=\|)', text)
		result_str = []
		if not re_object:
			result_str.append('Most reacted to posts\n')
			msgs = analytics.most_reacted_to_posts(self.message_manager)
		else:
			user_id = re_object.group(0)
			print(user_id)
			result_str.append('Most reacted to posts for ' + self.slack.get_user_name(user_id) + '\n')
			msgs = analytics.most_reacted_to_posts(self.message_manager, re_object.group(0))

		for msg in msgs:
			result_str.append(str(self.message_manager.get_message_text(msg[0])) + ' : ' + str(msg[1]) + '\n')

		res = ''.join(result_str)
		return ''.join(result_str)

	def on_most_used_reacts(self, text):
		user_id = re.search('(?<=\@)(.*?)(?=\|)', text)
		if not user_id:
			result = analytics.most_used_reacts(self.message_manager)
		else:
			result = analytics.favorite_reacts_of_user(self.message_manager, user_id.group(0))

		result_str = []
		for r in result:
			result_str.append(':')
			result_str.append(r[0])
			result_str.append(':')
			result_str.append(' : ' + str(r[1]) + '\n')
		return ''.join(result_str)
