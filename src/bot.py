import os
import sys
from multiprocessing import Queue
from multiprocessing import Process, Lock
import re
from slackclient import SlackClient
import analytics
from enum import Enum
import logging
from infinitetimer import InfiniteTimer
from util import React, Message, msg_id_string
import db
from time import sleep

MOST_USED_REACTS = 'most_used'
MOST_REACTED_TO_MESSAGES = 'most_reacted_to_messages'
MOST_UNIQUE_REACTS_ON_POST = 'most_unique'
REACT_BUZZWORDS = 'buzzwords'
MOST_REACTS = 'most_reacts'
COMMON_PHRASES = 'common_phrases'
MOST_ACTIVE = 'most_active'

VALID_COMMANDS = [MOST_USED_REACTS,
 				MOST_REACTED_TO_MESSAGES,
				MOST_UNIQUE_REACTS_ON_POST,
				REACT_BUZZWORDS,
				MOST_REACTS,
				COMMON_PHRASES,
				MOST_ACTIVE]

TIMER_INTERVAL = 2



authed_teams = {}
class Bot(object):
	oauth = {"client_id": os.environ.get("CLIENT_ID"),
				  "client_secret": os.environ.get("CLIENT_SECRET"),
				  # Scopes provide and limit permissions to what our app
				  # can access. It's important to use the most restricted
				  # scope that your app will need.
				  "scope": 'bot'}
	verification = os.environ.get("VERIFICATION_TOKEN")
	bot_client = SlackClient(os.environ.get('BOT_ACCESS_TOKEN'))
	workspace_client = SlackClient(os.environ.get('ACCESS_TOKEN'))
	event_queue = Queue()
	name = "reactanalyticsbot"
	emoji = ":robot_face:"
	users_lock = Lock()
	reacts_lock = Lock()
	users = {}
	channels = {}
	started = False
	reacts_list = set()


	@classmethod
	def start(cls):
		print('start')
		if not Bot.started:
			p = Process(target=Bot.event_handler_loop)
			p.start()
			Bot.started = True



	'''
	API INTERACTIONS
	'''

	@classmethod
	def load_users(cls):
		users_response = cls.workspace_client.api_call('users.list',
														scope=cls.oauth['scope'])
		if users_response['ok']:
			next_users = users_response['members']
			with cls.users_lock:
				for user in next_users:
					user_id = user['id']
					user_name = user['name']
					user_info = {'user_name' : user_name}
					if 'display_name' in user['profile']:
						user_info['display_name'] = user['profile']['display_name']
					else:
						user_info['display_name'] = user_name
					Bot.users[user_id] = user_info
		else:
			#raise Exception('Unable to load users: ' + )
			logging.getLogger(__name__).error(msg="Unable to load users: " + users_response['error'])

	# Given a channel ID checks if it's a direct message
	def is_dm_channel(self, channel_id):
		im_list_response = self.workspace_client.api_call('im.list')
		if im_list_response['ok']:
			im_channels = [im['id'] for im in im_list_response['ims']]
			return channel_id in im_channels
		else:
			return False

	@classmethod
	def load_reacts(cls):
		resp = cls.bot_client.api_call('emoji.list')
		if resp['ok']:
			with cls.reacts_lock:
				cls.reacts_list = {react for react in resp['emoji'].keys()}
		else:
			print('Failed to load reacts')
			print(resp)

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
		#with cls.lock:
		#	Bot.event_queue.put(evnt)
		cls.handle_event(evnt)

	@classmethod
	def handle_api_event(cls, event):
		print('handle_api_event')
		slack_event = event.event_info
		event_type = slack_event['event']['type']

		if 'subtype' in slack_event['event']:
			if slack_event['event']['subtype'] == 'message_deleted':
				event_type = 'message_deleted'



		if event_type == 'reaction_added':
			return cls.reaction_added(slack_event)
		elif event_type == 'reaction_removed':
			print('removed')
			return cls.reaction_removed(slack_event)
		elif event_type == 'message':
			print('onMessage')
			return cls.message_posted(slack_event)
		elif event_type == 'message_deleted':
			return cls.message_removed(slack_event)

	@classmethod
	def message_removed(slack_event):
		db.remove_message(Message('', slack_event['channel'], slack_event['ts'], '', ''))

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

		if not Bot.users:
			Bot.load_users()


		text = event['text'].split(' ')
		user_id = event['user_id']
		command = text[0]
		args = ""
		#check if there are any args
		if len(text) > 1:
			args = ' '.join(text[1:])
		try:
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
			elif command == COMMON_PHRASES:
				response = cls.common_phrases()
			elif command == MOST_ACTIVE:
				response = 'not implemented'#cls.most_active()
		except Exception as e:
			cls.send_dm(user_id, 'There was an error processing your request')
			raise e

		cls.send_dm(user_id, response)

	@classmethod
	def user_exists(cls, user):
		with cls.users_lock:
			if user in Bot.users:
				return True
			else:
				cls.load_users()
				return user in Bot.users

	@classmethod
	def common_phrases(cls):
		phrases = analytics.get_common_phrases()
		result_str = ['Common Phrases:\n']
		for p in phrases:
			result_str.append(' '.join(p[0]) + '\n')
		return ''.join(result_str)

	@classmethod
	def most_reacted_to_message(cls, text):
		re_object = re.search('(?<=\@)(.*?)(?=\|)', text)
		result_str = []
		if not re_object:
			result_str.append('Most reacted to posts\n:')
			msgs = analytics.most_reacted_to_posts()
		else:
			user_id = re_object.group(0)
			result_str.append('Most reacted to posts for ' + users[user_id] + '\n')
			msgs = analytics.most_reacted_to_posts(re_object.group(0))

		for msg in msgs:
			result_str.append(str(db.get_message_text('', msg[0])) + ' : ' + str(msg[1]) + '\n')

		return ''.join(result_str)

	@classmethod
	def most_reacts(cls, args):
		user_reacts = analytics.users_with_most_reacts()
		user_re = re.compile('(?<=\@)(.*?)(?=\|)')

		result_str = ['Users that react the most\n']
		for user, count in user_reacts.items():
			if cls.user_exists(user):
				result_str.append('<@' + user + '>: ' + str(count) + '\n')
			else:
				print(user + 'not in users dictionary')
		return ''.join(result_str)

	@classmethod
	def most_active(cls):
		most_active = dict(analytics.most_messages())
		result_str = ['Most active users:\n']
		print(most_active)
		for user in most_active:
			if cls.user_exists(user):
				result_str.append('<@' + user + '>\n')
			else:
				print(str(user) + 'not in users dictionary')
		return ''.join(result_str)

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

		for msg_id, reacts in result.items():
			text = db.get_message_text('', msg_id)
			if text:
				react_str = ''.join([':' + r + ': ' for r in reacts.keys()])
				result_str.append(text + ' : ' + react_str + '\n')

		return ''.join(result_str)

	@classmethod
	def react_buzzwords(cls, text):

		if not text.strip():
			return 'specify at least one react'

		result_str = []

		reacts = re.findall('(?<=:)(.*?)(?=:)', text)
		reacts = {r for r in reacts if r.strip(' ')}
		print(reacts)
		with cls.reacts_lock:
			if not all(r in cls.reacts_list for r in reacts):
				cls.load_reacts()
				missing_reacts = {r for r in reacts if r not in cls.reacts_list}
				if missing_reacts:
					result_str.append(' '.join(':' + r + ':' for r in missing_reacts))
					result_str.append(' not found.\n')
				reacts = reacts - missing_reacts


		try:
			for r in reacts:
				result_str.append(':'+r + ':: ')
				react_buzzwords = analytics.react_buzzword(r, Bot.users, Bot.channels, 10)

				if react_buzzwords:
					result_str.append(', '.join([word for word in react_buzzwords.keys()]) + '\n')
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
			with Bot.lock:
				event = Bot.event_queue.get()
				cls.handle_event(event)
			sleep(1)

	@classmethod
	def handle_event(cls, event):
		if event.type == EventType.API_EVENT:
			cls.handle_api_event(event)
		elif event.type == EventType.SLASH_COMMAND:
			cls.handle_slash_command(event)

class Event(object):
	def __init__(self, event_type, event_info):
		self.type = event_type
		self.event_info = event_info

class EventType(Enum):
	SLASH_COMMAND = 0
	API_EVENT = 1
