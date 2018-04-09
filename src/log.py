import inspect
import logging

logging.basicConfig(level=logging.WARNING)

def log_error(msg):
    log(msg, logging.ERROR)

def log_info(msg):
    log(msg, logging.INFO)

def log_debug(msg):
    log(msg, logging.DEBUG)

def log(msg, level):
    calling_function = inspect.stack()[2][3]
    logging.getLogger(__name__).log(level, 'From ' + calling_function + ": " + msg)