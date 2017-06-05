import logging
from handlers import sql_handler
from models import sql_logging
from dbsetup import _DEBUG

logger = logging.getLogger('SQL_log')

if _DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
hndlr = sql_handler.SQLAlchemyHandler()
if _DEBUG:
    hndlr.setLevel(logging.DEBUG)
else:
    hndlr.setLevel(logging.INFO)

hndlr.setFormatter(formatter)
logger.addHandler(hndlr)
