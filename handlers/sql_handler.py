import dbsetup
from models import sql_logging
import logging
import traceback

class SQLAlchemyHandler(logging.Handler):
    def emit(self, record):
        trace = None
        exc = record.__dict__['exc_info']
        if exc:
            trace = traceback.format_exc()
            if len(trace) > 2000:
                trace = trace[0:1999]

        log = sql_logging.Log(logger=record.__dict__['name'],
          level=record.__dict__['levelname'],
          trace=trace,
          msg=record.__dict__['msg'])

        session = dbsetup.Session()
        try:
            session.add(log)
            session.commit()
        finally:
            session.close()
