import sqlite3
import traceback

db_file = '/Users/noahwinston/ReactAnalytics/reacts_db.db'
auth_db = '/Users/noahwinston/ReactAnalytics/auth_db.db'


def add_auth_team(team_id, bot_access_code):
    conn = sqlite3.connect(auth_db)
    c = conn.cursor()

    c.execute('INSERT INTO AuthedTeams VALUES (?, ?)', (team_id, bot_access_code))
    conn.commit()
    conn.close()

def get_bot_token(team_id):
    conn = sqlite3.connect(auth_db)
    c = conn.cursor()

    select_result = c.execute('SELECT * FROM AuthedTeams WHERE TeamID = ?', (team_id, ))
    row = select_result.fetchone()
    conn.close()
    if row is None:
        return None

    return row[0]


def remove_message(msg_id):
    query = 'DELETE FROM MESSAGES WHERE MessageID = ?'

# msgs = (msg_id, team_id, user_id, text)
def add_messages(msgs):

    '''
    try:
        c.executemany('INSERT INTO Messages VALUES(?, ?, ?);', msgs)
    except Exception as e:
        print(e)
        print(traceback.print_exc())
    '''
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    for m in msgs:
        try:
            c.execute('INSERT INTO Messages VALUES (?, ?, ?, ?);', m)
        except Exception as e:
            print(e)
    conn.commit()
    conn.close()



def add_message(msg, conn=None):

    close = (conn is None)

    if not conn:
        conn = sqlite3.connect(db_file)
    c = conn.cursor()

    try:
        c.execute('INSERT INTO Messages VALUES (?, ?, ?, ?);',(msg))
    except Exception as e:
        print(e)
        print(traceback.print_exc())
    conn.commit()
    if close:
        conn.close()


# msgs = (msg_id, team_id, user_id, react_name)
def add_reacts(reacts):
    conn = sqlite3.connect(db_file)

    for react in reacts:
        msg_id = react[0]
        team_id = react[1]
        user_id = react[2]
        react_name = react[3]
        _add_react(conn, msg_id, team_id, user_id, react_name)
    conn.commit()
    conn.close()


def _add_react(conn, msg_id, team_id, user_id, react_name):
    c = conn.cursor()
    try:
        if _exists_in_message_reacts(conn, msg_id, react_name):
            query = ('''UPDATE MessageReacts
                    SET Count = Count + 1
                    WHERE MessageReacts.MessageID = ?
                    AND MessageReacts.ReactName = ?''')
            c.execute(query, (msg_id, react_name))
        else:
            c.execute('INSERT INTO MessageReacts VALUES(?, ?, 1);',(msg_id, react_name))

        if _exists_in_user_reacts(conn, user_id, react_name):
            c.execute('''UPDATE UserReacts
                    SET Count = Count + 1
                    WHERE UserReacts.UserID = ?
                    AND UserReacts.TeamID = ?
                    AND UserReacts.ReactName = ?''',
                      (user_id, team_id, react_name))
        else:
            c.execute('INSERT INTO UserReacts VALUES(?, ?, ?, 1);',(user_id, team_id, react_name))
    except Exception as e:
        print(e)
        print(traceback.print_exc())

def remove_react(msg_id, user_id, react_name):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    try:
        c.execute('''UPDATE MessageReacts
                SET Count = Count - 1
                WHERE MessageReacts.MessageID = ?
                AND MessageReacts.ReactName = ?''', (msg_id, react_name))
    except Exception as e:
        print(e)
        print(traceback.print_exc())

    try:
        c.execute('''
              UPDATE UserReacts
              SET Count = Count - 1
              WHERE UserReacts.UserID = ? AND UserReacts.ReactName = ?''', (user_id, react_name))
    except Exception as e:
        print(e)
        print(traceback.print_exc())

    conn.commit()
    conn.close()


def _exists_in_message_reacts(conn, msg_id, react_name):
    c = conn.cursor()
    result = c.execute("SELECT * FROM MessageReacts WHERE MessageReacts.MessageID = ? AND MessageReacts.ReactName = ?",
                       (msg_id, react_name))

    if result.fetchone() is None:
        return False
    return True


def _exists_in_user_reacts(conn, user_id, react_name):
    c = conn.cursor()
    result = c.execute(
        "SELECT * FROM UserReacts WHERE UserReacts.UserID = ? AND UserReacts.ReactName = ?",
        (user_id, react_name))
    if result.fetchone() is None:
        return False
    return True

def msg_exists(msg_id):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    result = c.execute('SELECT * FROM Messages WHERE MessageID = ?', (msg_id,))
    row = result.fetchone()
    conn.close()

    if row is None:
        return False
    return True


def get_reacts_on_user(user_id):
    msgs = get_messages_by_user(user_id)
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    msgs = [(m,) for m in msgs]

    result = c.executemany("SELECT ReactName, sum(MessageReacts.Count) FROM MessageReacts WHERE MessageID = ? GROUP BY ReactName", msgs)
    conn.close()
    return {r[0] : r[1] for r in result}

def get_reacts_by_user(user_id):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    result = c.execute(
        "SELECT UserReacts.ReactName, UserReacts.Count FROM UserReacts WHERE UserReacts.UserID = ?",(user_id, ))
    reacts = {r[0]: r[1] for r in result}
    conn.close()
    return reacts


def get_reacts_on_message(msg_id):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    result = c.execute(
        "SELECT MessageReacts.ReactName, MessageReacts.Count FROM MessageReacts WHERE MessageReacts.MessageID = ?",(
            msg_id, ))
    reacts = {r[0]: r[1] for r in result}
    conn.close()
    return reacts

def get_reacts_on_all_messages():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    result = c.execute("SELECT MessageReacts.ReactName, MessageReacts.Count FROM MessageReacts")
    reacts = {r[0] : r[1] for r in result}
    conn.close()
    return reacts


def get_messages_by_user(user_id):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    result = c.execute("SELECT MessageID FROM Messages WHERE Messages.UserID = ?", (user_id,))
    msgs = [row[0] for row in result]
    conn.close()
    return msgs


def get_message_text(team_id, msg_id, conn=None):

    query = "SELECT MessageText FROM Messages WHERE Messages.MessageID = ?"
    text = ""
    if not conn:
        conn = sqlite3.connect(db_file)
    c = conn.cursor()
    result = c.execute(query, (msg_id, ))
    msg = result.fetchone()
    if msg:
        text = msg[0]
    conn.close()
    return text

def get_all_message_texts():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    result = c.execute('SELECT MessageText from Messages')
    texts = [r[0] for r in result]
    conn.close()
    return texts

def get_message_text_from_ids(msg_ids):
    conn = sqlite3.connect(db_file)
    result = {msg_id: get_message_text(conn, msg_id) for msg_id in msg_ids}
    conn.close()
    return result

def get_message_ids():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    result = c.execute("SELECT MessageID FROM Messages")
    msg_ids = [r[0] for r in result]
    conn.close()
    return msg_ids

def get_react_counts():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    result = c.execute('SELECT ReactName, sum(MessageReacts.Count) from MessageReacts GROUP BY ReactName')
    reacts = {r[0] : r[1] for r in result}
    conn.close()
    return reacts

def get_react_count(react_name):

    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    query = 'SELECT sum(MessageReacts.Count) FROM MessageReacts WHERE ReactName = ?'
    result = c.execute(query, (react_name, ))
    conn.close()
    return [r[0] for r in result]

def get_messages_with_react(react_name, text=False):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    if text:
        query = '''
                  SELECT MessageText FROM Messages
                  INNER JOIN MessageReacts ON Messages.MessageID=MessageReacts.MessageID
                  WHERE MessageReacts.ReactName = ? AND MessageReacts.Count > 0
                  '''
    else:
        query = "SELECT MessageID FROM MessageReacts WHERE ReactName = ? AND Count > 0"


    result = c.execute(query, (react_name, ))
    msgs = [r[0] for r in result]
    conn.close()
    return msgs


