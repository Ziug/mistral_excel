import threading
import os
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

key = os.environ.get("KEY")
model = 'mistral-small-latest' 

message_history = []
session_timeout = 1800
session_timer = None

def reset_session_timer():
    global session_timer, message_history
    if session_timer:
        session_timer.cancel()
    session_timer = threading.Timer(session_timeout, end_session)
    session_timer.start()

def end_session():
    global message_history
    message_history = []
    print("\nСессия завершена из-за бездействия.")