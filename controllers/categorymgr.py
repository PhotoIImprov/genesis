import errno
from datetime import timedelta, datetime
from enum import Enum

from sqlalchemy import Column, Integer, DateTime, text, ForeignKey

import dbsetup
from cache.iiMemoize import memoize_with_expiry, _memoize_cache
from dbsetup import Base
from logsetup import logger
from models import resources
from models import usermgr, category, event
from cache.ExpiryCache import _expiry_cache

_CATEGORYLIST_MAXSIZE = 100

class CategoryManager():
    _start_date = None
    _duration_upload = None
    _duration_vote = None
    _description = None

    def __init__(self, **kwargs):
        if len(kwargs) == 0:
            return
        str_start_date = kwargs.get('start_date', None)
        if str_start_date is not None:
            self._start_date = datetime.strptime(str_start_date, '%Y-%m-%d %H:%M')
        self._duration_upload = kwargs.get('upload_duration', 24)
        self._duration_vote = kwargs.get('vote_duration', 72)
        self._description = kwargs.get('description', None)

        # validate arguments, start_date must be no more 5 minutes in the past
        if (type(self._duration_upload) is not int or self._duration_upload < 1 or self._duration_upload > 24*14) or \
           (type(self._duration_vote) is not int or self._duration_vote < 1 or self._duration_vote > 24 * 14) or \
           (datetime.now() - self._start_date).seconds > 300:
           raise Exception('CategoryManager', 'badargs')

    def create_resource(self, session, resource_string: str) -> resources.Resource:
        r = resources.Resource.find_resource_by_string(resource_string, 'EN', session)
        if r is not None:
            return r
        r = resources.Resource.create_new_resource(session, lang='EN', resource_str=resource_string)
        return r

    def create_category(self, session, type: int):

        # look up resource, see if we already have it
        r = self.create_resource(session, self._description)
        if r is None:
            return None

        # we have stashed (or found) our name, time to create the category
        c = category.Category(upload_duration=self._duration_upload, vote_duration=self._duration_vote, start_date=self._start_date, rid=r.resource_id, type=type)
        session.add(c)
        return c

    def active_categories_for_user(self, session, au):
        """
        ActiveCategoriesForUser()
        return a list of "active" categories for this user.

        "Active" means PENDING/VOTING/UPLOAD/COUNTING states
        "for User" means all open (public) categories and any categoties
        in events this user is participating in.
        :param session:
        :param u: an AnonUser object
        :return: <list> of categories
        """
        open_cl = category.Category.all_categories(session, au)
        try:
            q = session.query(category.Category). \
                join(event.EventCategory,event.EventCategory.category_id == category.Category.id). \
                join(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
                filter(category.Category.state != category.CategoryState.CLOSED.value) . \
                filter(event.EventUser.active == True) . \
                filter(event.EventCategory.active == True). \
                filter(event.EventUser.user_id == au.id)
            event_cl  = q.all()
        except Exception as e:
            logger.exception(msg="error reading event category list for user:{}".format(u.id))
            raise

        if event_cl is None or len(event_cl) == 0:
            return open_cl

        # need to combine our lists
        combined_cl = open_cl + event_cl

        return combined_cl

class EventManager():
    _nl = [] # list of resources (strings)
    _cm_list = [] # list of categories manager objects that will create our categories
    _cl = [] # list of categories we created
    _e = None # our event object
    _ec_list = []
    _eu = None

    def __init__(self, **kwargs):
        self._nl = kwargs.get('categories', None)
        if self._nl is None:
            raise Exception('CategoryManager', 'badargs')

        vote_duration = kwargs.get('vote_duration', None)
        upload_duration = kwargs.get('upload_duration', None)
        start_date = kwargs.get('start_date', None)
        self._e = event.Event(**kwargs)

        self._cm_list = []
        for n in self._nl:
            c = CategoryManager(description=n, start_date=start_date, upload_duration=upload_duration, vote_duration=vote_duration)
            self._cm_list.append(c)

    def create_event(self, session) -> event.Event:

        passphrases = PassPhraseManager().select_passphrase(session)
        self._e.accesskey = passphrases
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
                ec = event.EventCategory(category=c, event=self._e, active=True)
                session.add(ec)
                self._ec_list.append(ec)

            # Tie the "creator" to the Event/Categories. If the creator is a player, they are "active" and can play
            self._eu = event.EventUser(user=self._e._u, event=self._e, active=(self._e._u.usertype == usermgr.UserType.PLAYER.value))
            session.add(self._eu)

            session.commit()    # now Category/Event/EventCategory/EventUser records all created, save them to the DB

        except Exception as e:
            logger.exception(msg="error creating event categories")

        return self._e

class PassPhraseManager():

    def select_passphrase(self, session) -> str:
        try:
            q = session.query(event.AccessKey). \
                filter(event.AccessKey.used == False). \
                order_by(event.AccessKey.hash). \
                with_for_update()

            ak = q.first()
            ak.used = True
            session.commit()
            return ak.passphrase
        except Exception as e:
            raise Exception('select_passphrase', 'no phrases!')
