import errno
from datetime import timedelta, datetime
from enum import Enum

from sqlalchemy import Column, Integer, DateTime, text, ForeignKey

import dbsetup
from cache.iiMemoize import memoize_with_expiry, _memoize_cache
from dbsetup import Base
from logsetup import logger
from models import resources
from models import usermgr, category, event, engagement, photo
from cache.ExpiryCache import _expiry_cache
from sqlalchemy import exists
from sqlalchemy import func

_CATEGORYLIST_MAXSIZE = 100

class CategoryManager():
    _start_date = None
    _duration_upload = None
    _duration_vote = None
    _description = None

    def __init__(self, **kwargs):
        if len(kwargs) == 0:
            return
        try:
            str_start_date = kwargs.get('start_date', None)
            if str_start_date is not None:
                self._start_date = datetime.strptime(str_start_date, '%Y-%m-%d %H:%M')
        except ValueError as ve:
            msg = "error with date/time format {0}, format should be YYYY-MM-DD HH:MM, UTC time".format(str_start_date)
            logger.excepion(msg=msg)
            raise

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
            # q = session.query(category.Category). \
            #     join(event.EventCategory,event.EventCategory.category_id == category.Category.id). \
            #     join(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
            #     filter(category.Category.state != category.CategoryState.CLOSED.value) . \
            #     filter(event.EventUser.active == True) . \
            #     filter(event.EventCategory.active == True). \
            #     filter(event.EventUser.user_id == au.id)

            q = session.query(category.Category). \
                join(event.EventCategory,event.EventCategory.category_id == category.Category.id). \
                join(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
                filter(category.Category.state != category.CategoryState.CLOSED.value) . \
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

    _PHOTOLIST_MAXSIZE = 100
    def category_photo_list(self, session, dir: str, pid: int, cid: int) -> list:
        '''
        return a list of photos for the specified category
        :param session:
        :param pid: recent photo id to fetch from
        :param dir: "next" or "prev"
        :param cid: category identifier
        :return:
        '''
        try:
            if (dir == 'next'):
                q = session.query(photo.Photo). \
                    filter(photo.Photo.category_id == cid). \
                    filter(photo.Photo.id > pid). \
                    order_by(photo.Photo.id.asc())
            else:
                q = session.query(photo.Photo). \
                    filter(photo.Photo.category_id == cid). \
                    filter(photo.Photo.id < pid). \
                    order_by(photo.Photo.id.desc())

            pl = q.all()
        except Exception as e:
            raise

        return pl[:self._PHOTOLIST_MAXSIZE]

    def photo_dict(self, pl: list) -> list:
        d_photos = []
        for p in pl:
            d_photos.append(p.to_dict())

        return d_photos

    @staticmethod
    def next_category_start(session) -> str:
        q = session.query(func.max(category.Category.start_date). \
            filter(Category.state.in_(
            [CategoryState.UPLOAD.value, CategoryState.VOTING.value, CategoryState.COUNTING.value,
             CategoryState.UNKNOWN.value])). \
            filter(Category.type == CategoryType.OPEN.value) )

        c = q.one()
        return c.end_date

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

    @staticmethod
    def join_event(session, accesskey: str, au: usermgr.AnonUser) -> event.Event:
        try:
            # q = session.query(event.Event).\
            #     join(event.EventCategory, event.EventCategory.event_id == event.Event.id). \
            #     join(category.Category, category.Category.id == event.EventCategory.category_id). \
            #     filter(event.Event.accesskey == accesskey). \
            #     filter(category.Category.state != category.CategoryState.CLOSED.value)
            q = session.query(event.Event).\
                filter(event.Event.accesskey == accesskey)
            e = q.one_or_none()
            if e is None:
                raise Exception('join_event', 'event not found') # no such event

            # we have an event the user can join, so we need to create an EventUser
            # see if it already exists...
            q = session.query(event.EventUser). \
                filter(event.EventUser.user_id == au.id). \
                filter(event.EventUser.event_id == e.id)
            eu = q.one_or_none()
            if eu is None:
                eu = event.EventUser(user=au, event=e, active=True)
                session.add(eu)

            # get the categories for this event
            q = session.query(category.Category). \
                join(event.EventCategory, event.EventCategory.category_id == category.Category.id).\
                filter(event.EventCategory.event_id == e.id)
            e._cl = q.all()

            return e
        except Exception as e:
            logger.exception(msg='error joining event')
            raise

        raise Exception('join_event', 'fatal error')

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

    @staticmethod
    def event_details(session, au: usermgr.AnonUser, event_id: int) -> list:
        try:
            e = session.query(event.Event).get(event_id)
            cl = e.read_categories(session)
            cl_dict = []
            for c in cl:
                (num_photos, num_users) = EventManager.category_details(session, c)
                c_dict = c.to_json()
                c_dict['num_players'] = num_users
                c_dict['num_photos'] = num_photos
                cl_dict.append(c_dict)

            e_dict = e.to_dict()
            e_dict['categories'] = cl_dict
            return e_dict
        except Exception as e:
            logger.exception(msg="error fetching event {0}".format(event_id))
            raise

        return None

    @staticmethod
    def category_details(session, c: category.Category):
        try:
            num_photos = photo.Photo.count_by_category(session, c.id)
            num_users = photo.Photo.count_by_users(session, c.id)
            return (num_photos, num_users)
        except Exception as e:
            raise

    @staticmethod
    def events_for_user(session, au: usermgr.AnonUser) -> list:
        try:
            q = session.query(event.Event). \
                join(event.EventUser, event.EventUser.event_id == event.Event.id). \
                join(event.EventCategory, event.EventCategory.event_id == event.Event.id). \
                join(category.Category, category.Category.id == event.EventCategory.category_id). \
                filter(event.EventUser.user_id == au.id). \
                filter(category.Category.state.in_([category.CategoryState.UPLOAD.value, category.CategoryState.VOTING.value, category.CategoryState.COUNTING.value, category.CategoryState.UNKNOWN.value]))

#            q = session.query(event.EventUser).filter(event.EventUser.user_id == au.id)
            el = q.all()

            # for each event, read in the categories
            d_el = []
            for e in el:
                e.read_categories(session)
                d_el.append(e.to_dict())

            return d_el # a dictionary suitable for jsonification
        except Exception as e:
            logger.exception(msg="events_for_user() failed to get event user list")
            raise


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

class RewardManager():
    _user_id = None
    _rewardtype = None
    def __init__(self, **kwargs):
        self._user_id = kwargs.get('user_id', None)
        self._rewardtype = kwargs.get('rewardtype', None)

    def create_reward(self, session, quantity: int) -> None:
        try:
            r = engagement.Reward(user_id=self._user_id, rewardtype=self._rewardtype, quantity=quantity)
            session.add(r)

            ur_l = session.query(engagement.UserReward).filter(user_id = self._user_id).filter(rewardtype = self._rewardtype).all()
            if ur_l is not None:
                ur = ur_l[0]
            if ur is None:
                ur = engagement.UserReward(user_id=self.user_id, rewardtype=self._rewardtype, quantity=0)

            ur.update_quantity(quantity)
            session.add(ur)
        except Exception as e:
            logger.exception(msg="error updating reward quantity")
            raise

class FeedbackManager():

    _uid = None
    _pid = None
    _like = False
    _offensive = False
    _tags = None

    def __init__(self, **kwargs):
        self._uid = kwargs.get('uid', None)
        self._pid = kwargs.get('pid', None)
        self._like = kwargs.get('like', False)
        self._offensive = kwargs.get('offensive', False)
        self._tags = kwargs.get('tags', None)

    def create_feedback(self, session) -> None:
        try:
            fb = session.query(engagement.Feedback).filter(engagement.Feedback.user_id == self._uid).filter(engagement.Feedback.photo_id == self._pid).one_or_none()
            if fb is None:
                fb = engagement.Feedback(uid=self._uid, pid=self._pid, like=self._like, offensive=self._offensive)
            else:
                fb.update_feedback(like=self._like, offensive=self._offensive)
            session.add(fb)

            if self._tags is not None:
                ft = session.query(engagement.FeedbackTag).filter(engagement.FeedbackTag.user_id == self._uid).filter(engagement.FeedbackTag.photo_id == self._pid).one_or_none()
                if ft is None:
                    ft = engagement.FeedbackTag(uid=self._uid, pid=self._pid, tags=self._tags)
                else:
                    ft.update_feedbacktags(self._tags)

                session.add(ft)

            fb.update_photo(session, self._pid)
        except Exception as e:
            logger.exception(msg="error creating feedback entry")
            raise
