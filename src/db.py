import traceback
import os
import log
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor


CREATE_MESSAGES_TABLE = '''CREATE TABLE IF NOT EXISTS Messages (
    MessageID  varchar(40) PRIMARY KEY,
    UserID     varchar(40),
    Text       TEXT)
'''

CREATE_REACTS_TABLE = '''CREATE TABLE IF NOT EXISTS Reacts (
  MessageID    varchar(40),
  UserID       varchar(40),
  ReactName    varchar(40),
  FOREIGN KEY (MessageID) REFERENCES Messages (MessageID))
'''
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def create_tables(conn):
    try:
        cursor = conn.cursor
        cursor.execute(CREATE_MESSAGES_TABLE)
        cursor.execute(CREATE_REACTS_TABLE)
    except Exception as e:
        pass
    finally:
        conn.commit()

def psycopg2_cur(func):
    '''
    DB connection handler
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            create_tables(conn)
            ret_val = func(cursor, *args, **kwargs)
        finally:
            conn.commit()
            conn.close()
        return ret_val
    return wrapper



@psycopg2_cur
def remove_message(cursor, msg):
    if not msg:
        return
    query = 'DELETE FROM Messages WHERE MessageID = %s'
    cursor.execute(query, (msg.msg_id,))


@psycopg2_cur
def add_message(cursor, msg):
    if not msg:
        return
    try:
        cursor.execute('INSERT INTO Messages VALUES (%s, %s, %s);',
                       (msg.msg_id, msg.user_id, msg.text))
    except Exception as e:
        print(e)
        print(traceback.print_exc())


@psycopg2_cur
def execute(cursor, query, args=None):
    cursor.execute(query, args)
    result = []
    row = cursor.fetchone()
    while row:
        result.append(row)
        row = cursor.fetchone()
    return result



@psycopg2_cur
def add_react(cursor, react):
    if not react:
        return
    try:
        cursor.execute('INSERT INTO Reacts VALUES(%s, %s, %s);', (react.msg_id, react.user_id, react.name))
    except Exception as e:
        print(e)
        print(traceback.print_exc())




@psycopg2_cur
def remove_react(cursor, react):
    if not react:
        return
    args = (react.msg_id, react.user_id, react.name)
    cursor.execute('''DELETE FROM Reacts WHERE MessageID=%s
                    AND UserID=%s AND ReactName=%s;''', args)






@psycopg2_cur
def get_message_text_from_ids(cursor, msg_ids):
    query = "SELECT MessageText FROM Messages WHERE Messages.MessageID = %s"
    result = {}
    for msg_id in msg_ids:
        cursor.execute(query, (msg_id, ))
        row = cursor.fetchone()
        if not row:
            continue
        result[msg_id] = row[0]
    return result


