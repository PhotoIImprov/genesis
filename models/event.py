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

    _u = None
    _cl = None
    def __init__(self, **kwargs):
        self._u = kwargs.get('user', None)
        self.user_id = self._u.id
        self.accesskey = kwargs.get('accesskey', None)
        self.num_players = kwargs.get('max_players', 5)
        self.active = kwargs.get('active', True)
        self.name = kwargs.get('name', None)

    def read_categories(self, session):
        try:
            q = session.query(category.Category). \
                join(EventCategory, EventCategory.category_id == category.Category.id). \
                filter(EventCategory.event_id == self.id)
            self._cl = q.all()
        except Exception as e:
            logger.exception(msg="error reading categories for Event {0}".format(self.id))
            raise

    def to_dict(self) -> dict:
        d_cl = []
        for c in self._cl:
            d_cl.append(c.to_json())
        return {'accesskey': self.accesskey, 'max_players': self.num_players, 'name': self.name, 'active': self.active, 'created_by': str(self.user_id), 'categories': d_cl, 'created': self.created_date.strftime("%Y-%m-%d %H:%M")}

class EventUser(Base):
    __tablename__ = 'eventuser'
    event_id = Column(Integer, ForeignKey("event.id", name="fk_eventuser_event_id"), nullable=False, primary_key=True)
    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_eventuser_user_id"), nullable=False, primary_key=True)
    active = Column(Boolean, default=True, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))


    def __init__(self, **kwargs):
        u = kwargs.get('user', None)
        e = kwargs.get('event', None)
        self.user_id = u.id
        self.event_id = e.id
        self.active = kwargs.get('active', True)

class EventCategory(Base):
    __tablename__ = 'eventcategory'
    event_id = Column(Integer, ForeignKey("event.id", name="fk_eventcategory_event_id"), nullable=False, primary_key=True)
    category_id = Column(Integer, ForeignKey("category.id", name="fk_eventcategory_category_id"), nullable=False, primary_key=True)
    active = Column(Boolean, default=True, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, **kwargs):
        c = kwargs.get('category', None)
        e = kwargs.get('event', None)
        self.category_id = c.id
        self.event_id = e.id
        self.active = kwargs.get('active', True)

class AccessKey(Base):
    __tablename__ = 'accesskey'

    id = Column(Integer, nullable=False, primary_key=True, autoincrement=True)
    passphrase = Column(String(20), nullable=False)
    used = Column(Boolean, default=True, nullable=False)
    hash = Column(String(32), nullable=False)

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', None)
        self.phassphrase = kwargs.get('passphrase', None)
        self.used = kwargs.get('used', False)
