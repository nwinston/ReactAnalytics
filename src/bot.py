import os
import sys
from multiprocessing import Queue
from threading import Thread
import re
from slackclient import SlackClient
import analytics
from enum import Enum
import logging
from infinitetimer import InfiniteTimer
from util import React, Message
import db

MOST_USED_REACTS = 'most_used'
MOST_REACTED_TO_MESSAGES = 'most_reacted_to_messages'
MOST_UNIQUE_REACTS_ON_POST = 'most_unique'
REACT_BUZZWORDS = 'buzzwords'
MOST_REACTS = 'most_reacts'

VALID_COMMANDS = [MOST_USED_REACTS, MOST_REACTED_TO_MESSAGES, MOST_UNIQUE_REACTS_ON_POST, REACT_BUZZWORDS, MOST_REACTS]

TIMER_INTERVAL = 2

authed_teams = {}
class Bot(object):
	def __init__(self):
		super(Bot, self).__init__()
		self.name = "reactanalyticsbot"
		self.emoji = ":robot_face:"
		# When we instantiate a new bot object, we can access the app
		# credentials we set earlier in our local development environment.
		self.oauth = {"client_id": os.environ.get("CLIENT_ID"),
					  "client_secret": os.environ.get("CLIENT_SECRET"),
					  # Scopes provide and limit permissions to what our app
					  # can access. It's important to use the most restricted
					  # scope that your app will need.
					  "scope": 'bot'}
		self.verification = os.environ.get("VERIFICATION_TOKEN")
		self.bot_client = SlackClient(os.environ.get('BOT_ACCESS_TOKEN'))
		self.workspace_client = SlackClient(os.environ.get('ACCESS_TOKEN'))
		self.users = {} # user_id : {'user_name' : user_name, 'display_name' : display_name}
		self.channels = {} #channel_id : channel_name

		self.event_queue = Queue()
		self.message_posted_queue = Queue()
		self.react_event_queue = Queue()
		self.load_users()
		event_thread = Thread(target=self.event_handler_loop)
		event_thread.start()
		#t = Thread(self._on_init())
		#t.start()
		print('start')

	def _on_init(self):
		msgs, reacts = self.load_message_history()

		# dont add messages already in db
		msgs = [msg for msg in msgs if not db.msg_exists(msg.msg_id)]
		reacts = [react for react in reacts if not db.msg_exists(react.msg_id)]
		db.add_messages(msgs)
		db.add_reacts(reacts)


	'''
	API INTERACTIONS
	'''


	def load_users(self):
		users_response = self.workspace_client.api_call('users.list',
														scope=self.oauth['scope'])
		if users_response['ok']:
			users = users_response['members']
			for user in users:
				user_id = user['id']
				user_name = user['name']
				user_info = {'user_name' : user_name}
				if 'display_name' in user['profile']:
					user_info['display_name'] = user['profile']['display_name']
				self.users[user_id] = user_info
		else:
			#raise Exception('Unable to load users: ' + )
			logging.getLogger(__name__).error(msg="Unable to load users: " + users_response['error'])

	def load_channels(self):
		list_response = self.workspace_client.api_call('channels.list')
		if not list_response['ok']:
			logging.getLogger(__name__).error(msg='Failed to get channel list: ' + list_response['error'])
			return
		for channel in list_response['channels']:
			self.channels[channel['id']] = channel['name']

	def load_message_history(self):
		team_info_response = self.workspace_client.api_call('team.info',
															scope=self.oauth['scope'])
		if team_info_response['ok']:
			team_id = team_info_response['team']['id']
		else:
			return []
		if not self.channels:
			self.load_channels()
		messages = []
		reacts = []
		for channel in self.channels:
			channel_msgs = self.get_channel_message_history(channel)
			for msg in channel_msgs:
				ts = msg['ts']
				if 'user' not in msg:
					continue
				msg_user = msg['user']
				msg_text = msg['text']
				if 'reactions' in msg:
					reacts_on_msg = msg['reactions']
					for r in reacts_on_msg:
						name = r['name']
						reacts.extend(React(team_id, channel, ts, react_user, name) for react_user in r['users'])

				messages.append(Message(team_id, channel, ts, msg_user, msg_text))
		return messages, reacts

	def get_channel_message_history(self, channel_id):
		messages = []
		has_more = True
		latest = 0
		while has_more:
			try:
				response = self.workspace_client.api_call('channels.history',
													  channel=channel_id,
													  latest = latest)
			except:
				return messages
			if not response['ok']:
				logging.getLogger(__name__).error(
					msg='Failed to get channel history for ' + channel_id + ': ' + response['error'])
				return []
			messages.extend(response['messages'])
			if messages:
				latest = messages[-1]['ts']
			has_more = response['has_more']
		return messages

	# Given a channel ID checks if it's a direct message
	def is_dm_channel(self, channel_id):
		im_list_response = self.workspace_client.api_call('im.list')
		if im_list_response['ok']:
			im_channels = [im['id'] for im in im_list_response['ims']]
			return channel_id in im_channels
		else:
			return False

	def send_dm(self, user_id, message):
		new_dm = self.bot_client.api_call('im.open',
										  user=user_id)

		if not new_dm['ok']:
			return False

		channel_id = new_dm['channel']['id']
		post_msg = self.bot_client.api_call('chat.postMessage',
											channel=channel_id,
											username=self.name,
											text=message)
		return post_msg['ok']

	def auth(self, code):
		response = self.bot_client.api_call('oauth.access',
											client_id=self.oauth['client_id'],
											client_secret=self.oauth['client_secret'],
											code=code)
		if response['ok']:
			team_id = response['team_id']
			bot_token = response['bot']['bot_access_token']
			self.bot_client = SlackClient(bot_token)




	def auth_token(self, token):
		auth_response = self.workspace_client.api_call('auth.test',
												 token=token)
		return auth_response['ok']

	'''
	EVENT HANDLERS
	'''

	def on_event(self, event_type, slack_event):
		self.event_queue.put(Event(event_type, slack_event))

	def handle_api_event(self, event):
		slack_event = event.event_info
		event_type = slack_event['event']['type']



		if event_type == 'reaction_added':
			return self.reaction_added(slack_event)
		elif event_type == 'reaction_removed':
			print('removed')
			return self.reaction_removed(slack_event)
		elif event_type == 'message':
			print('onMessage')
			return self.message_posted(slack_event)

	def reaction_added(self, slack_event):
		event = slack_event['event']
		react_name = event['reaction']
		user_id = event['user']
		channel_id = event['item']['channel']
		time_stamp = event['item']['ts']
		db.add_react(React('', channel_id, time_stamp, user_id, react_name))

	def reaction_removed(self, slack_event):
		event = slack_event['event']
		react_name = event['reaction']
		user_id = event['user']
		channel_id = event['item']['channel']
		time_stamp = event['item']['ts']

		db.remove_react(React('',channel_id, time_stamp, user_id, react_name))

	def message_posted(self, slack_event):
		try:
			event = slack_event['event']
			channel_id = event['channel']
		#if self.is_dm_channel(channel_id):
		#	return
			user_id = event['user']
			time_stamp = event['ts']
			text = event['text']
			msg = Message('', channel_id, time_stamp, user_id, text)
			db.add_message(msg)
		except:
			logging.getLogger(__name__).error('Failed to unpack slack event')


	def post_to_db(self):
		msgs = []
		while not self.message_posted_queue.empty():
			msgs.append(self.message_posted_queue.get())
		db.add_messages(msgs)

		reacts = []
		while not self.react_event_queue.empty():
			reacts.append(self.react_event_queue.get())
		db.add_reacts(reacts)


	def handle_slash_command(self, event):
		event = event.event_info
		token = event['token']

		if not self.auth_token(token):
			logging.getLogger(__name__).warning('Not authed')
			return



		text = event['text'].split(' ')
		user_id = event['user_id']
		command = text[0]
		args = ""
		#check if there are any args
		if len(text) > 1:
			args = ' '.join(text[1:])

		if command == MOST_USED_REACTS:
			response = self.most_used_reacts(args)
		elif command == MOST_REACTED_TO_MESSAGES:
			response = self.most_reacted_to_message(args)
		elif command == MOST_UNIQUE_REACTS_ON_POST:
			response = self.most_unique_reacts_on_post(args)
		elif command == REACT_BUZZWORDS:
			response = self.react_buzzwords(args)
		elif command == MOST_REACTS:
			response = self.most_reacts(args)

		print(response)
		self.send_dm(user_id, response)


	def most_reacted_to_message(self, text):
		re_object = re.search('(?<=\@)(.*?)(?=\|)', text)
		result_str = []
		if not re_object:
			result_str.append('Most reacted to posts\n:')
			msgs = analytics.most_reacted_to_posts()
		else:
			user_id = re_object.group(0)
			result_str.append('Most reacted to posts for ' + self.users[user_id] + '\n')
			msgs = analytics.most_reacted_to_posts(re_object.group(0))

		for msg in msgs:
			result_str.append(str(db.get_message_text('', msg[0])) + ' : ' + str(msg[1]) + '\n')

		return ''.join(result_str)

	def most_reacts(self, args):
		users = analytics.users_with_most_reacts()


	def most_used_reacts(self, text):
		user_id = re.search('(?<=\@)(.*?)(?=\|)', text)
		if not user_id:
			result = analytics.most_used_reacts()
		else:
			result = analytics.favorite_reacts_of_user(user_id.group(0))

		result_str = ['Most used reacts:\n']
		for r in result:
			result_str.append(':')
			result_str.append(str(r[0]))
			result_str.append(':')
			result_str.append(' : ' + str(r[1]) + '\n')
		return ''.join(result_str)

	def most_unique_reacts_on_post(self, text):
		channel_id = re.search('(?<=\#)(.*?)(?=\|)', text)
		result_str = []
		if not channel_id:
			result = analytics.most_unique_reacts_on_a_post()
		else:
			result = analytics.most_unique_reacts_on_a_post(channel_id.group(0))

		for r in result:
			text = db.get_message_text('', r[0])
			if text:
				result_str.append(text + ' : ' + str(r[1]) + '\n')

		return ''.join(result_str)

	def reacts_to_words(self, text):
		return ' '.join(analytics.reacts_to_words(self.users, self.channels))

	def react_buzzwords(self, text):

		reacts = re.findall('(?<=:)(.*?)(?=:)', text)
		reacts = [r for r in reacts if r.strip(' ')]
		result_str = []

		try:
			for r in reacts:
				result_str.append(':'+r + ':: ')
				react_buzzwords = [item[0] for item in analytics.react_buzzword(r, self.users, self.channels, 20)]

				if react_buzzwords:
					result_str.append(', '.join(react_buzzwords) + '\n')
				else:
					result_str.append('React not used\n')

		except Exception as e:
			logging.getLogger(__name__).exception(e.message, e.args)
			return 'something went wrong'

		return ''.join(result_str)


	def event_handler_loop(self):
		while True:
			while not self.event_queue.empty():
				event = self.event_queue.get()
				if event.type == EventType.API_EVENT:
					self.handle_api_event(event)
				elif event.type == EventType.SLASH_COMMAND:
					self.handle_slash_command(event)



class Event(object):
	def __init__(self, event_type, event_info):
		self.type = event_type
		self.event_info = event_info

class EventType(Enum):
	SLASH_COMMAND = 0
	API_EVENT = 1
