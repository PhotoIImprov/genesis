import logging
from handlers import sql_handler
from models import sql_logging
from dbsetup import _DEBUG
import time
from functools import wraps

logger = logging.getLogger('SQL_log')
client_logger = logging.getLogger('Client_log')

if _DEBUG:
    logger.setLevel(logging.DEBUG)
    client_logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
    client_logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
hndlr = sql_handler.SQLAlchemyHandler()
if _DEBUG:
    hndlr.setLevel(logging.DEBUG)
else:
    hndlr.setLevel(logging.INFO)

hndlr.setFormatter(formatter)
logger.addHandler(hndlr)
client_logger.addHandler(hndlr)

def timeit():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            ts = time.time()
            result = fn(*args, **kwargs)
            te = time.time()
            logger.info( msg='TIMER:{0}:{1}'.format(fn.__name__, te - ts))
            return result
        return decorator
    return wrapper