import traceback
import os
import psycopg2
import log
from functools import wraps

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def psycopg2_cur(func):
    '''
    DB connection handler
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            ret_val = func(cursor, *args, **kwargs)
        finally:
            conn.commit()
            conn.close()
        return ret_val
    return wrapper

@psycopg2_cur
def remove_message(cursor, msg):
    query = 'DELETE FROM MESSAGES WHERE MessageID = %s'
    cursor.execute(query, (msg.msg_id,))


@psycopg2_cur
def add_message(cursor, msg):
    try:
        cursor.execute('INSERT INTO Messages VALUES (%s, %s, %s, %s);',
                       (msg.msg_id, msg.team_id, msg.user_id, msg.text))
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
    _add_react(cursor, react.msg_id, react.team_id,
               react.user_id, react.react_name)


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
    try:
        cursor.execute('''UPDATE MessageReacts
                SET Count = Count - 1
                WHERE MessageReacts.MessageID = %s
                AND MessageReacts.ReactName = %s''', (react.msg_id, react.react_name))
    except Exception as e:
        print(e)
        print(traceback.print_exc())

    try:
        cursor.execute('''
              UPDATE UserReacts
              SET Count = Count - 1
              WHERE UserReacts.UserID = %s AND UserReacts.ReactName = %s''', (react.user_id, react.react_name))
    except Exception as e:
        print(e)
        print(traceback.print_exc())





@psycopg2_cur
def get_message_text_from_ids(cursor, msg_ids):
    query = "SELECT MessageText FROM Messages WHERE Messages.MessageID = %s"
    result = {}
    for msg_id in msg_ids:
        cursor.execute(query, (msg_id, ))
        row = cursor.fetchone()
        if not row:
            print('not row')
            continue
        result[msg_id] = row[0]
    return result


