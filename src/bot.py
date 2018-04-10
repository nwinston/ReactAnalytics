import os
import sys
from queue import Queue
from threading import Thread, Lock
import re
from slackclient import SlackClient
import analytics
from enum import Enum
import logging
from infinitetimer import InfiniteTimer
from util import React, Message
import db
from time import sleep

MOST_USED_REACTS = 'most_used'
MOST_REACTED_TO_MESSAGES = 'most_reacted_to_messages'
MOST_UNIQUE_REACTS_ON_POST = 'most_unique'
REACT_BUZZWORDS = 'buzzwords'
MOST_REACTS = 'most_reacts'

VALID_COMMANDS = [MOST_USED_REACTS, MOST_REACTED_TO_MESSAGES, MOST_UNIQUE_REACTS_ON_POST, REACT_BUZZWORDS, MOST_REACTS]

TIMER_INTERVAL = 2

authed_teams = {}
class Bot(object):
	event_queue = Queue()
	oauth = {"client_id": os.environ.get("CLIENT_ID"),
				  "client_secret": os.environ.get("CLIENT_SECRET"),
				  # Scopes provide and limit permissions to what our app
				  # can access. It's important to use the most restricted
				  # scope that your app will need.
				  "scope": 'bot'}
	verification = os.environ.get("VERIFICATION_TOKEN")
	bot_client = SlackClient(os.environ.get('BOT_ACCESS_TOKEN'))
	workspace_client = SlackClient(os.environ.get('ACCESS_TOKEN'))
	users = {}  # user_id : {'user_name' : user_name, 'display_name' : display_name}
	channels = {}  # channel_id : channel_name
	name = "reactanalyticsbot"
	emoji = ":robot_face:"

	lock = Lock()
	def __init__(self):
		super(Bot, self).__init__()

		# When we instantiate a new bot object, we can access the app
		# credentials we set earlier in our local development environment.

		Bot.load_users()
		#Bot.event_thread = Thread(target=Bot.event_handler_loop)
		#Bot.event_thread.start()


	'''
	API INTERACTIONS
	'''

	@classmethod
	def load_users(cls):
		users_response = cls.workspace_client.api_call('users.list',
														scope=cls.oauth['scope'])
		if users_response['ok']:
			users = users_response['members']
			for user in users:
				user_id = user['id']
				user_name = user['name']
				user_info = {'user_name' : user_name}
				if 'display_name' in user['profile']:
					user_info['display_name'] = user['profile']['display_name']
				cls.users[user_id] = user_info
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

	@classmethod
	def send_dm(cls, user_id, message):
		new_dm = cls.bot_client.api_call('im.open',
										  user=user_id)

		if not new_dm['ok']:
			return False

		channel_id = new_dm['channel']['id']
		post_msg = cls.bot_client.api_call('chat.postMessage',
											channel=channel_id,
											username=cls.name,
											text=message)
		return post_msg['ok']

	@classmethod
	def auth(cls, code):
		response = cls.bot_client.api_call('oauth.access',
											client_id=cls.oauth['client_id'],
											client_secret=cls.oauth['client_secret'],
											code=code)
		if response['ok']:
			team_id = response['team_id']
			bot_token = response['bot']['bot_access_token']
			cls.bot_client = SlackClient(bot_token)



	@classmethod
	def auth_token(cls, token):
		auth_response = cls.workspace_client.api_call('auth.test',
												 token=token)
		return auth_response['ok']

	'''
	EVENT HANDLERS
	'''

	@classmethod
	def on_event(cls, event_type, slack_event):
		evnt = Event(event_type, slack_event)
		cls.event_queue.put(evnt)
		print(cls.event_queue.qsize())
		print('count: ' + str(Event.count))

	@classmethod
	def handle_api_event(cls, event):
		print('handle_api_event')
		slack_event = event.event_info
		event_type = slack_event['event']['type']



		if event_type == 'reaction_added':
			return cls.reaction_added(slack_event)
		elif event_type == 'reaction_removed':
			print('removed')
			return cls.reaction_removed(slack_event)
		elif event_type == 'message':
			print('onMessage')
			return cls.message_posted(slack_event)

	@staticmethod
	def reaction_added(slack_event):
		print('reaction_added')
		event = slack_event['event']
		react_name = event['reaction']
		user_id = event['user']
		channel_id = event['item']['channel']
		time_stamp = event['item']['ts']
		db.add_react(React('', channel_id, time_stamp, user_id, react_name))

	@staticmethod
	def reaction_removed(slack_event):
		event = slack_event['event']
		react_name = event['reaction']
		user_id = event['user']
		channel_id = event['item']['channel']
		time_stamp = event['item']['ts']

		db.remove_react(React('',channel_id, time_stamp, user_id, react_name))

	@staticmethod
	def message_posted(slack_event):
		print('message_posted')
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



	@classmethod
	def handle_slash_command(cls, event):
		print('handle_slash_command')
		event = event.event_info
		token = event['token']

		if not cls.auth_token(token):
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
			response = cls.most_used_reacts(args)
		elif command == MOST_REACTED_TO_MESSAGES:
			response = cls.most_reacted_to_message(args)
		elif command == MOST_UNIQUE_REACTS_ON_POST:
			response = cls.most_unique_reacts_on_post(args)
		elif command == REACT_BUZZWORDS:
			response = cls.react_buzzwords(args)
		elif command == MOST_REACTS:
			response = cls.most_reacts(args)

		cls.send_dm(user_id, response)

	@classmethod
	def most_reacted_to_message(cls, text):
		re_object = re.search('(?<=\@)(.*?)(?=\|)', text)
		result_str = []
		if not re_object:
			result_str.append('Most reacted to posts\n:')
			msgs = analytics.most_reacted_to_posts()
		else:
			user_id = re_object.group(0)
			result_str.append('Most reacted to posts for ' + cls.users[user_id] + '\n')
			msgs = analytics.most_reacted_to_posts(re_object.group(0))

		for msg in msgs:
			result_str.append(str(db.get_message_text('', msg[0])) + ' : ' + str(msg[1]) + '\n')

		return ''.join(result_str)

	@classmethod
	def most_reacts(cls, args):
		users = analytics.users_with_most_reacts()

	@classmethod
	def most_used_reacts(cls, text):
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

	@classmethod
	def most_unique_reacts_on_post(cls, text):
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

	@classmethod
	def reacts_to_words(cls, text):
		return ' '.join(analytics.reacts_to_words(cls.users, cls.channels))

	@classmethod
	def react_buzzwords(cls, text):

		reacts = re.findall('(?<=:)(.*?)(?=:)', text)
		reacts = [r for r in reacts if r.strip(' ')]
		result_str = []

		try:
			for r in reacts:
				result_str.append(':'+r + ':: ')
				react_buzzwords = [item[0] for item in analytics.react_buzzword(r, cls.users, cls.channels, 20)]

				if react_buzzwords:
					result_str.append(', '.join(react_buzzwords) + '\n')
				else:
					result_str.append('React not used\n')

		except Exception as e:
			logging.getLogger(__name__).exception(e.message, e.args)
			return 'something went wrong'

		return ''.join(result_str)

	@classmethod
	def event_handler_loop(cls):
		print('event_handler_loop')
		while True:

			while not cls.event_queue.empty():
				event = cls.event_queue.get()
				cls.handle_event(event)
				cls.event_queue.task_done()
				sleep(10)

	@classmethod
	def handle_event(cls, event):
		if event.type == EventType.API_EVENT:
			cls.handle_api_event(event)
		elif event.type == EventType.SLASH_COMMAND:
			cls.handle_slash_command(event)

class Event(object):
	count = 0
	def __init__(self, event_type, event_info):
		print('event: ' + str(event_type))
		self.type = event_type
		self.event_info = event_info
		Event.inc()

	@classmethod
	def inc(cls):
		cls.count += 1

	def __del__(self):
		print('del event: ' + str(self.type))

	def __str__(self):
		print('event: ' + str(self.type))

class EventType(Enum):
	SLASH_COMMAND = 0
	API_EVENT = 1
