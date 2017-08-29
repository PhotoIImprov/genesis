from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, Boolean, String
import dbsetup
from dbsetup import Base
from logsetup import logger
from models import usermgr, category

class Event(Base):
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_event_userid"), nullable=False)
    accesskey = Column(String(32), nullable=False)
    num_players = Column(Integer, default=5, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    name = Column(String(100), nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id', None)
        self.accesskey = kwargs.get('accesskey', None)
        self.max_players = kwargs.get('max_players', 5)
        self.active = kwargs.get('active', True)
        self.name = kwargs.get('name', None)

class EventUser(Base):
    __tablename__ = 'eventuser'
    event_id = Column(Integer, ForeignKey("event.id", name="fk_eventuser_event_id"), nullable=False, primary_key=True)
    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_eventuser_user_id"), nullable=False, primary_key=True)
    active = Column(Boolean, default=True, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))


    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id', None)
        self.event_id = kwargs.get('event_id', None)
        self.active = kwargs.get('active', True)

class EventCategory(Base):
    __tablename__ = 'eventcategory'
    event_id = Column(Integer, ForeignKey("event.id", name="fk_eventcategory_event_id"), nullable=False, primary_key=True)
    category_id = Column(Integer, ForeignKey("anonuser.id", name="fk_eventcategory_user_id"), nullable=False, primary_key=True)
    active = Column(Boolean, default=True, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id', None)
        self.category_id = kwargs.get('category_id', None)
        self.active = kwargs.get('active', True)

class EventManager():
    _nl = [] # list of resources (strings)
    _cl = [] # list of categories
    _e = None # our event object

    def __init__(self, **kwargs):
        self._nl = kwargs.get('categories', None)
        if self._nl is None:
            raise

        vote_duration = kwargs.get('vote_duration', None)
        upload_duration = kwargs.get('upload_duration', None)
        start_date = kwargs.get('start_date', None)
        self._e = Event(kwargs)

        self._cl = []
        for n in nl:
            c = category.CategoryManager(description=n, start_date=e.start_date, upload_duration=upload_duration, vote_duration=vote_duration)
            self._cl.append(c)

    def create_event(self, session):

        for cm in self._cl:
            None
