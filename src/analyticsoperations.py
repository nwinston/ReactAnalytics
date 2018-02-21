from threading import Thread
'''
class AnalyticsOperations(object):
	#So we know who to return the result on the specified thread to
	def __init__(self):
		self.pool = ThreadPool()
		self.user_mapping = {} # thread_id : user_id

	def add_operation(self, function, user_id, **kwargs):
		result = self.pool.apply_async(function, kwargs, callback=send_result)

	def send_result(self, pyBot, user_id, msg_text):
'''

class AnalyticsThread(Thread):
	def __init__(self, f, text, user_id, pyBot, app):
		Thread.__init__(self)
		self.user_id = user_id
		self.pyBot = pyBot
		self.text = text
		self.function = f
		self.app = app

	def run(self):
		with self.app.test_request_context():
			res = self.function(self.text)
			self.pyBot.send_dm(self.user_id, res)