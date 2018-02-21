from slackclient import SlackClient
import os
import yaml
class Slack(object):
	def __init__(self, access_token):
		self.user_token = access_token
		self.oauth = {'client_id' : os.environ.get('CLIENT_ID'),
		 'client_secret' : os.environ.get('CLIENT_SECRET')}
		self.verification = os.environ.get('VERIFICATION_TOKEN')
		self.slack = SlackClient(self.user_token)
		self.users = {} # 'user_id' : 'user_name'
		self.get_all_messages()

	def auth_token(self, token):
		response = self.slack.api_call('auth.test',
			token=token)
		return response['ok']

	def api_call(api_function, **kwargs):
		return self.slack.api_call(api_function, kwargs)

	def get_all_messages(self):
		list_response = self.slack.api_call('channels.list')
		if not list_response['ok']:
			print(list_response)
			raise Exception('Failed to get channel list: ' + list_response['error'])
		channels = [c['id'] for c in list_response['channels']]
		messages = {}
		for channel in channels:
			messages[channel] = self.get_channel_history(channel)
		return messages

	def get_channel_history(self, channel_id):
		response = self.slack.api_call('channels.history',
				channel=channel_id)
		if response['ok']:
			return response['messages']
		else:
			print (response['error'])
			raise Exception('Failed to get channel history: ' + response['error'])

	def get_all_users(self):
		users_response = self.slack.api_call('users.list')
		if users_response['ok']:
			users = users_response['members']
			for user in users:
				user_id = user['id']
				name = user['name']
				self.users[user_id] = name
		else:
			print(users_response['error'])
			raise Exception("Unable to get users: " + users_response['error'])

	def get_user_name(self, user_id):
		if user_id not in self.users:
			try:
				self.get_all_users()
			except:
				return None
		return self.users.get(user_id, None)