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
    def __init__(self, **kwargs):
        self._u = kwargs.get('user', None)
        self.user_id = self._u.id
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
        u = kwargs.get('user', None)
        e = kwargs.get('event', None)
        self.user_id = u.id
        self.event_id = e.id
        self.active = kwargs.get('active', True)

class EventCategory(Base):
    __tablename__ = 'eventcategory'
    event_id = Column(Integer, ForeignKey("event.id", name="fk_eventcategory_event_id"), nullable=False, primary_key=True)
    category_id = Column(Integer, ForeignKey("anonuser.id", name="fk_eventcategory_user_id"), nullable=False, primary_key=True)
    active = Column(Boolean, default=True, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, **kwargs):
        c = kwargs.get('category', None)
        e = kwargs.get('event', None)
        self.category_id = c.id
        self.event_id = e.id
        self.active = kwargs.get('active', True)

class EventManager():
    _nl = [] # list of resources (strings)
    _cm_list = [] # list of categories manager objects that will create our categories
    _cl = [] # list of categories we created
    _e = None # our event object

    def __init__(self, **kwargs):
        self._nl = kwargs.get('categories', None)
        if self._nl is None:
            raise

        vote_duration = kwargs.get('vote_duration', None)
        upload_duration = kwargs.get('upload_duration', None)
        start_date = kwargs.get('start_date', None)
        self._e = Event(**kwargs)

        self._cm_list = []
        for n in self._nl:
            c = category.CategoryManager(description=n, start_date=start_date, upload_duration=upload_duration, vote_duration=vote_duration)
            self._cm_list.append(c)

    def create_event(self, session):

        session.add(self._e)

        try:
            self._cl = []
            for cm in self._cm_list:
                c = cm.create_category(session, type=category.CategoryType.EVENT.value)
                self._cl.append(c)

            session.commit() # we need Event.id and Category.id values, so commit these objects to the DB

            # the event and all it's categories are created, so we have PKs,
            # time to make the EventCategory entries
            for c in self._cl:
                ec = EventCategory(category=c, event=self._e, active=True)
                session.add(ec)

            # Tie the "creator" to the Event/Categories. If the creator is a player, they are "active" and can play
            eu = EventUser(user=u, event=self._e, active=(self._e._u.usertype == usermgr.UserType.PLAYER.value))
            session.add(eu)

            session.commit()    # now Category/Event/EventCategory/EventUser records all created, save them to the DB

        except Exception as e:
            logger.exception(msg="error creating event categories")
        finally:
            session.close()