import traceback
import os
import psycopg2
import log
from functools import wraps

DATABASE_URL = os.environ.get('DATABASE_URL')


def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')


def psycopg2_cur(func):
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
def add_messages(cursor, msgs):
    for m in msgs:
        if not msg_exists(m.msg_id):
            try:
                msg_tuple = (m.msg_id, m.team_id, m.user_id, m.text)
                cursor.execute(
                    'INSERT INTO Messages VALUES (%s, %s, %s, %s);', msg_tuple)
            except Exception as e:
                log.log_error(e.message)


@psycopg2_cur
def add_message(cursor, msg):
    try:
        cursor.execute('INSERT INTO Messages VALUES (%s, %s, %s, %s);',
                       (msg.msg_id, msg.team_id, msg.user_id, msg.text))
    except Exception as e:
        print(e)
        print(traceback.print_exc())


@psycopg2_cur
def add_reacts(cursor, reacts):
    log.log_info('add_reacts')
    for react in reacts:
        _add_react(cursor, react.msg_id, react.team_id,
                   react.user_id, react.react_name)


@psycopg2_cur
def add_react(cursor, react):
    _add_react(cursor, react.msg_id, react.team_id,
               react.user_id, react.react_name)


def _add_react(cursor, msg_id, team_id, user_id, react_name):
    try:
        if _exists_in_message_reacts(cursor, msg_id, react_name):
            query = ('''UPDATE MessageReacts
                    SET Count = Count + 1
                    WHERE MessageReacts.MessageID = %s
                    AND MessageReacts.ReactName = %s''')
            cursor.execute(query, (msg_id, react_name))
        else:
            cursor.execute(
                'INSERT INTO MessageReacts VALUES(%s, %s, 1);', (msg_id, react_name))

        if _exists_in_user_reacts(cursor, user_id, react_name):
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
    log.log_info('remove_react')

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


def _exists_in_message_reacts(cursor, msg_id, react_name):
    cursor.execute("SELECT * FROM MessageReacts WHERE MessageReacts.MessageID = %s AND MessageReacts.ReactName = %s",
                   (msg_id, react_name))
    result = cursor.fetchone()
    if not result:
        return False
    return True


def _exists_in_user_reacts(cursor, user_id, react_name):
    cursor.execute(
        "SELECT * FROM UserReacts WHERE UserReacts.UserID = %s AND UserReacts.ReactName = %s",
        (user_id, react_name))
    result = cursor.fetchone()
    if not result:
        return False
    return True


@psycopg2_cur
def msg_exists(cursor, msg_id):
    cursor.execute('SELECT * FROM Messages WHERE MessageID = %s', (msg_id,))
    row = cursor.fetchone()
    exists = False
    if row:
        exists = True
    return exists


@psycopg2_cur
def get_reacts_on_user(cursor, user_id):
    msgs = get_messages_by_user(user_id)
    msgs = [(m,) for m in msgs]

    cursor.executemany(
        "SELECT ReactName, sum(MessageReacts.Count) FROM MessageReacts WHERE MessageID = %s GROUP BY ReactName", msgs)
    row = cursor.fetchone()
    reacts = {}
    while row:
        reacts[row[0]] = row[1]
        row = cursor.fetchone()
    return reacts


@psycopg2_cur
def get_reacts_by_user(cursor, user_id):
    cursor.execute(
        "SELECT UserReacts.ReactName, UserReacts.Count FROM UserReacts WHERE UserReacts.UserID = %s", (user_id, ))
    row = cursor.fetchone()
    reacts = {}
    while row:
        reacts[row[0]] = row[1]
        row = cursor.fetchone()
    return reacts


@psycopg2_cur
def get_react_usage_totals(cursor):
    cursor.execute('SELECT UserID, sum(Count) FROM UserReacts GROUP BY UserID')
    users = {}
    row = cursor.fetchone()
    while row:
        users[row[0]] = row[1]
        row = cursor.fetchone()
    return users


@psycopg2_cur
def get_reacts_on_message(cursor, msg_id, conn=None):
    cursor.execute(
        "SELECT ReactName, Count FROM MessageReacts WHERE MessageID = %s", (
            msg_id, ))
    row = cursor.fetchone()
    reacts = {}
    while row:
        reacts[row[0]] = row[1]
        row = cursor.fetchone()
    return reacts


@psycopg2_cur
def get_reacts_on_all_messages(cursor):
    cursor.execute(
        "SELECT MessageReacts.MessageID, MessageReacts.ReactName, MessageReacts.Count FROM MessageReacts")
    row = cursor.fetchone()
    reacts = {}
    while row:
        msg_id = row[0]
        react_name = row[1]
        count = row[2]
        if msg_id not in reacts:
            reacts[msg_id] = {}
        reacts[msg_id][react_name] = count
        row = cursor.fetchone()
    return reacts


@psycopg2_cur
def get_messages_by_user(cursor, user_id):
    cursor.execute(
        "SELECT MessageID FROM Messages WHERE Messages.UserID = %s", (user_id,))
    row = cursor.fetchone()
    msgs = []
    while row:
        msgs.append(row[0])
        row = cursor.fetchone()
    return msgs


@psycopg2_cur
def get_message_text(cursor, team_id, msg_id):
    query = "SELECT MessageText FROM Messages WHERE Messages.MessageID = %s"
    cursor.execute(query, (msg_id, ))
    result = cursor.fetchone()
    if not result:
        return ''

    text = result[0]
    return text


@psycopg2_cur
def get_all_message_texts(cursor):
    cursor.execute('SELECT MessageText from Messages')
    row = cursor.fetchone()
    texts = []
    while row:
        texts.append(row[0])
        row = cursor.fetchone()
    return texts


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


@psycopg2_cur
def get_message_ids(cursor):
    cursor.execute("SELECT MessageID FROM Messages")
    row = cursor.fetchone()
    msg_ids = []
    while row:
        msg_ids.append(row[0])
        row = cursor.fetchone()
    return msg_ids


@psycopg2_cur
def get_react_counts(cursor):
    cursor.execute(
        'SELECT ReactName, SUM(MessageReacts.Count) FROM MessageReacts GROUP BY ReactName')
    row = cursor.fetchone()
    reacts = {}
    while row:
        reacts[row[0]] = row[1]
        row = cursor.fetchone()
    return reacts


@psycopg2_cur
def get_react_count(cursor, react_name):
    query = 'SELECT sum(MessageReacts.Count) FROM MessageReacts WHERE ReactName = %s'
    cursor.execute(query, (react_name, ))
    row = cursor.fetchone()
    count = []
    while row:
        count.append(row[0])
        row = cursor.fetchone()
    return count


@psycopg2_cur
def get_messages_with_react(cursor, react_name, text=False):
    if text:
        query = '''
                  SELECT MessageText FROM Messages
                  INNER JOIN MessageReacts ON Messages.MessageID=MessageReacts.MessageID
                  WHERE MessageReacts.ReactName = %s AND MessageReacts.Count > 0
                  '''
    else:
        query = "SELECT MessageID FROM MessageReacts WHERE ReactName = %s AND Count > 0"

    cursor.execute(query, (react_name, ))
    row = cursor.fetchone()
    msgs = []
    while row:
        msgs.append(row[0])
        row = cursor.fetchone()
    return msgs


@psycopg2_cur
def get_message_table(cursor):
    cursor.execute('SELECT * FROM Messages')
    row = cursor.fetchone()
    msgs = []
    while row:
        msgs.append(row)
        row = cursor.fetchone()
    return msgs


@psycopg2_cur
def get_user_reacts_table(cursor):
    cursor.execute('SELECT * FROM UserReacts')
    row = cursor.fetchone()
    reacts = []
    while row:
        reacts.append(row)
        row = cursor.fetchone()
    return reacts


@psycopg2_cur
def execute(cursor, query, args=None):
    cursor.execute(query, args)
    result = []
    row = cursor.fetchone()
    while row:
        result.append(row)
        row = cursor.fetchone()
    return result
