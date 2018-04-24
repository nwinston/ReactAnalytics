import os
from multiprocessing import Queue
from multiprocessing import Process, Lock
import re
from slackclient import SlackClient
import analytics
import logging
from util import React, Message
import db
from time import sleep

EVENT_TYPE_SLASH_COMMAND = 0
EVENT_TYPE_API_EVENT = 1

MOST_USED_REACTS = 'most_used'
MOST_REACTED_TO_MESSAGES = 'most_reacted_to'
MOST_UNIQUE_REACTS_ON_POST = 'most_unique'
REACT_BUZZWORDS = 'buzzwords'
MOST_REACTS = 'most_reacts'
COMMON_PHRASES = 'common_phrases'
MOST_ACTIVE = 'most_active'

VALID_COMMANDS = {MOST_USED_REACTS : '[_optional_ *@User*]',
                  MOST_UNIQUE_REACTS_ON_POST : '[_optional_ *@User*]',
                                MOST_REACTED_TO_MESSAGES : '[_optional_ *@User*]',
                                REACT_BUZZWORDS : '[_required_ :react:, :react2: ...]',
                                MOST_REACTS : '',
                                COMMON_PHRASES : '',
                                MOST_ACTIVE : ''}

TIMER_INTERVAL = 2



authed_teams = {}
class Bot(object):
	def __init__(self):
		self.oauth = {"client_id": os.environ.get("CLIENT_ID"),
				 "client_secret": os.environ.get("CLIENT_SECRET"),
				 # Scopes provide and limit permissions to what our app
				 # can access. It's important to use the most restricted
				 # scope that your app will need.
				 "scope": 'bot'}
		self.verification = os.environ.get("VERIFICATION_TOKEN")
		self.bot_client = SlackClient(os.environ.get('BOT_ACCESS_TOKEN'))
		self.workspace_client = SlackClient(os.environ.get('ACCESS_TOKEN'))
		self.event_queue = Queue()
		self.name = "reactanalyticsbot"
		self.emoji = ":robot_face:"
		self.users_lock = Lock()
		self.reacts_lock = Lock()
		self.users = {}
		self.channels = {}
		self.reacts_list = set()
		self.start()

	
	def start(self):
		p = Process(target=self.event_handler_loop)
		p.start()

	'''
	API INTERACTIONS
	'''
	
	def verify_token(self, token):
		return self.verification == token

	
	def load_users(self):
		users_response = self.workspace_client.api_call('users.list',
														scope=self.oauth['scope'])

		if not users_response['ok']:
			print('Failed to load users')
			print(users_response)
			return

		should_continue = True
		while should_continue:
			next_users = users_response['members']
			with self.users_lock:
				for user in next_users:
					user_id = user['id']
					user_name = user['name']
					user_info = {'user_name' : user_name}
					if 'display_name' in user['profile']:
						user_info['display_name'] = user['profile']['display_name']
					else:
						user_info['display_name'] = user_name
					self.users[user_id] = user_info
			if 'response_metadata' in users_response:
				next_cursor = users_response['response_metadata']['next_cursor']

				if not next_cursor:
					should_continue = False
				else:
					users_response = self.workspace_client.api_call('users.list',
																	scope=self.oauth['scope'],
																	cursor=next_cursor)
					should_continue = users_response['ok']
			else:
				should_continue = False

	# Given a channel ID checks if it's a direct message
	def is_dm_channel(self, channel_id):
		im_list_response = self.workspace_client.api_call('im.list')
		if im_list_response['ok']:
			im_channels = [im['id'] for im in im_list_response['ims']]
			return channel_id in im_channels
		else:
			return False

	
	def load_reacts(self):
		resp = self.workspace_client.api_call('emoji.list')
		if resp['ok']:
			with self.reacts_lock:
				self.reacts_list = {react for react in resp['emoji'].keys()}
		else:
			print('Failed to load reacts')
			print(resp)

	
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

	
	def on_event(self, token, event_type, slack_event):
		if self.verify_token(token):
			evnt = Event(event_type, slack_event)
			self.event_queue.put(evnt)
		else:
			return False

	
	def handle_api_event(self, event):
		print('handle_api_event')
		slack_event = event.event_info
		event_type = slack_event['event']['type']

		if 'subtype' in slack_event['event']:
			if slack_event['event']['subtype'] == 'message_deleted':
				event_type = 'message_deleted'



		if event_type == 'reaction_added':
			return self.reaction_added(slack_event)
		elif event_type == 'reaction_removed':
			return self.reaction_removed(slack_event)
		elif event_type == 'message':
			return self.message_posted(slack_event)
		elif event_type == 'message_deleted':
			return self.message_removed(slack_event)

	
	def message_removed(self, slack_event):
		db.remove_message(Message('', slack_event['channel'], slack_event['ts'], '', ''))

	@staticmethod
	def reaction_added(slack_event):
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



	
	def handle_slash_command(self, event):
		event = event.event_info
		token = event['token']

		if not self.auth_token(token):
			logging.getLogger(__name__).warning('Not authed')
			return

		if not self.users:
			self.load_users()


		text = event['text'].split(' ')
		user_id = event['user_id']
		command = text[0]
		args = ""

		#check if there are any args
		if len(text) > 1:
			args = ' '.join(text[1:])
		try:
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
			elif command == COMMON_PHRASES:
				response = self.common_phrases()
			elif command == MOST_ACTIVE:
				response = self.most_active()
		except Exception as e:
			self.send_dm(user_id, 'There was an error processing your request')
			raise e

		self.send_dm(user_id, response)

	
	def user_exists(self, user):
		if user in self.users:
			return True
		else:
			self.load_users()
			return user in self.users

	
	def common_phrases(self):
		phrases = analytics.get_common_phrases()
		print(phrases)
		result_str = ['Common Phrases:\n']
		for p in phrases:
			result_str.append(' '.join(p) + '\n')
		return ''.join(result_str)

	
	def most_reacted_to_message(self, text):
		re_object = re.search('(?<=\@)(.*?)(?=\|)', text)
		result_str = []
		if not re_object:
			result_str.append('Most reacted to posts:\n')
			msgs = analytics.most_reacted_to_posts()
		else:
			user_id = re_object.group(0)
			result_str.append('Most reacted to posts for ' + self.users[user_id] + ':\n')
			msgs = analytics.most_reacted_to_posts(re_object.group(0))

		for msg, count in msgs.items():
			result_str.append(str(db.get_message_text('', msg)) + ' : ' + str(count) + '\n')

		return ''.join(result_str)

	
	def most_reacts(self, args):
		user_reacts = analytics.users_with_most_reacts()

		result_str = ['Users that react the most\n']
		for user, count in user_reacts.items():
			if self.user_exists(user):
				result_str.append('<@' + user + '>: ' + str(count) + '\n')
			else:
				print(user + 'not in users dictionary')
		return ''.join(result_str)

	
	def most_active(self):
		most_active = analytics.most_active()
		result_str = ['Most active users:\n']
		for user in most_active:
			if self.user_exists(user):
				result_str.append('<@' + user + '>\n')
			else:
				print(str(user) + 'not in users dictionary')
		return ''.join(result_str)

	
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
		result_str = ['Messages with most unique reacts:\n']
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

	
	def react_buzzwords(self, text):

		if not text.strip():
			return 'specify at least one react'

		result_str = []

		reacts = re.findall('(?<=:)(.*?)(?=:)', text)
		reacts = {r for r in reacts if r.strip(' ')}

		try:
			for r in reacts:
				result_str.append(':'+r + ':: ')
				react_buzzwords = analytics.react_buzzword(r, self.users, self.channels, 10)

				if react_buzzwords:
					result_str.append(', '.join([word for word in react_buzzwords.keys()]) + '\n')
				else:
					result_str.append('React not used\n')

		except Exception as e:
			logging.getLogger(__name__).exception(e.message, e.args)
			return 'something went wrong'

		return ''.join(result_str)

	
	def event_handler_loop(self):
		print('start event loop')
		while True:
			while not self.event_queue.empty():
				event = self.event_queue.get()
				self.handle_event(event)
			sleep(1)

	
	def handle_event(self, event):
		if event.type == EVENT_TYPE_API_EVENT:
			self.handle_api_event(event)
		elif event.type == EVENT_TYPE_SLASH_COMMAND:
			self.handle_slash_command(event)

class Event(object):
	def __init__(self, event_type, event_info):
		self.type = event_type
		self.event_info = event_info
