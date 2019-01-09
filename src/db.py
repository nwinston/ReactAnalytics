import traceback
import os
import psycopg2
import log
from functools import wraps


CREATE_MESSAGES_TABLE = '''CREATE TABLE Messages (
    MessageID  varchar(40) PRIMARY KEY,
    UserID     varchar(40),
    Text       TEXT)
'''

CREATE_REACTS_TABLE = '''CREATE TABLE Reacts (
  MessageID    varchar(40),
  UserID       varchar(40),
  ReactName    varchar(40),
  FOREIGN KEY (MessageID) REFERENCES Messages (MessageID))
'''
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def create_tables(cursor):
    try:
        cursor.execute(CREATE_MESSAGES_TABLE)
        cursor.execute(CREATE_REACTS_TABLE)
    except Exception as e:
        print(e)

def psycopg2_cur(func):
    '''
    DB connection handler
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            create_tables(cursor)
            ret_val = func(cursor, *args, **kwargs)
        finally:
            conn.commit()
            conn.close()
        return ret_val
    return wrapper



@psycopg2_cur
def remove_message(cursor, msg):
    query = 'DELETE FROM Messages WHERE MessageID = %s'
    cursor.execute(query, (msg.msg_id,))


@psycopg2_cur
def add_message(cursor, msg):
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
    cursor.execute('INSERT INTO MessageReacts VALUES(%s, %s, %s);', (react.msg_id, react.user_id, react.name))


def _add_react(cursor, msg_id, team_id, user_id, react_name):
    def _exists_in_message_reacts(msg_id, react_name):
        cursor.execute("SELECT * FROM MessageReacts WHERE MessageReacts.MessageID = %s AND MessageReacts.ReactName = %s",
                       (msg_id, react_name))
        result = cursor.fetchone()
        if not result:
            return False
        return True


    def _exists_in_user_reacts(user_id, react_name):
        cursor.execute(
            "SELECT * FROM UserReacts WHERE UserReacts.UserID = %s AND UserReacts.ReactName = %s",
            (user_id, react_name))
        result = cursor.fetchone()
        if not result:
            return False
        return True




    try:
        if _exists_in_message_reacts(msg_id, react_name):
            query = ('''UPDATE MessageReacts
                    SET Count = Count + 1
                    WHERE MessageReacts.MessageID = %s
                    AND MessageReacts.ReactName = %s''')
            cursor.execute(query, (msg_id, react_name))
        else:
            cursor.execute(
                'INSERT INTO MessageReacts VALUES(%s, %s, 1);', (msg_id, react_name))

        if _exists_in_user_reacts(user_id, react_name):
            cursor.execute('''UPDATE UserReacts
                    SET Count = Count + 1
                    WHERE UserReacts.UserID = %s
                    AND UserReacts.TeamID = %s
                    AND UserReacts.ReactName = %s''',
                           (user_id, team_id, react_name))
        else:
            cursor.execute(
                'INSERT INTO UserReacts VALUES(%s, %s, %s, 1);', (user_id, team_id, react_name))
    except Exception as e:
        print(e)
        print(traceback.print_exc())


@psycopg2_cur
def remove_react(cursor, react):
    args = (react.msg_id, react.user_id, react.react_name)
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


