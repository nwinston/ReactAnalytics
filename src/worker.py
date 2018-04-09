import os
import redis
from rq import Worker, Queue, Connection
import log

listen = ['default']

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

conn = redis.from_url(redis_url)

if __name__ == '__main__':
    log.log_info('Starting worker')
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()