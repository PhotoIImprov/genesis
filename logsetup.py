import logging
from handlers import sql_handler
from models import sql_logging

logger = logging.getLogger('SQL_log')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
hndlr = sql_handler.SQLAlchemyHandler()
hndlr.setLevel(logging.DEBUG)
hndlr.setFormatter(formatter)
logger.addHandler(hndlr)
