from sqlalchemy import Column, text
from sqlalchemy.types import DateTime, Integer, String
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from dbsetup import Base
import os

class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    host = Column(String(100), index=True, nullable=False)
    logger = Column(String(200))
    level = Column(String(64), index=True, nullable=False)
    trace = Column(String(2000))
    msg = Column(String(500))

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    def __init__(self, logger=None, level=None, trace=None, msg=None):
        self.logger = logger
        self.level = level
        self.trace = trace
        self.msg = msg
        self.host = str.upper(os.uname()[1])

    def __unicode__(self):
        return self.__repr__()

    def __repr__(self):
        return "<Log: %s - %s>" % (self.created_date.strftime('%m/%d/%Y-%H:%M:%S'), self.msg[:50])

