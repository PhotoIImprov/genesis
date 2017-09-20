import errno
from datetime import timedelta, datetime
from enum import Enum

from sqlalchemy import Column, Integer, DateTime, text, ForeignKey

import dbsetup
from cache.iiMemoize import memoize_with_expiry, _memoize_cache
from dbsetup import Base
from logsetup import logger
from models import resources
from models import usermgr, category, event, engagement, photo, voting
from cache.ExpiryCache import _expiry_cache
from sqlalchemy import exists
from sqlalchemy import func
from logsetup import timeit
from random import randint, shuffle
import redis
from leaderboard.leaderboard import Leaderboard
from models import error
from dbsetup import Configuration
import json

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
            logger.exception(msg=msg)
            raise

        self._duration_upload = kwargs.get('upload_duration', 24)
        self._duration_vote = kwargs.get('vote_duration', 72)
        self._description = kwargs.get('description', None)

        # timedelta.seconds is a magnitude
        dtnow = datetime.now()
        time_difference = (dtnow - self._start_date).seconds
        if self._start_date > dtnow:
            time_difference = 0 - time_difference

        # validate arguments, start_date must be no more 5 minutes in the past
        if (type(self._duration_upload) is not int or self._duration_upload < 1 or self._duration_upload > 24*14) or \
           (type(self._duration_vote) is not int or self._duration_vote < 1 or self._duration_vote > 24 * 14) or \
           (time_difference > 300):
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
    def next_category_start(session) -> datetime:
        # find the last category to finish with uploading, that's when we need to start this one
        q = session.query(func.max(func.date_add(category.Category.start_date, text("INTERVAL duration_upload HOUR")))).\
            filter(category.Category.state.in_([category.CategoryState.UPLOAD.value, category.CategoryState.UNKNOWN.value])).\
            filter(category.Category.type == category.CategoryType.OPEN.value)

        last_date = q.all()
        dt_last = datetime.strptime(last_date[0][0], '%Y-%m-%d %H:%M:%S')
        return dt_last

    @staticmethod
    def copy_photos_from_previous_categories(session, cid: int) -> int:
        '''
        Copy photo records from previous categories of the same name
        We'll call our stored procedure to do this work
        '''
        stored_proc = 'CALL sp_CopyCategories(:cid)'
        results = session.execute(stored_proc, {'cid': cid})

        num_photos = photo.Photo.count_by_category(session, cid)
        return num_photos

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

            e_dict = e.to_dict(au.id)
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
                e.read_userinfo(session)
                d_el.append(e.to_dict(au.id))

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

class RewardManager():
    _uid = None
    _type = None
    def __init__(self, **kwargs):
        self._uid = kwargs.get('uid', None)
        self._type = kwargs.get('type', None)

    def spend(self, session, quantity: int) -> engagement.UserReward:
        try:
            q = session.query(engagement.UserReward). \
                filter(engagement.UserReward.user_id == self._uid). \
                filter(engagement.UserReward.rewardtype == self._type)
            ur = q.one()

            if not ur.decrement_quantity(quantity=quantity):
                raise Exception('insufficient awards', ur.current_balance)
            return ur
        except Exception as e:
            logger.exception(msg='[rewardmgr] error making award')
            raise

    def award(self, session, quantity: int, dt_now = datetime.now()) -> engagement.UserReward:
        # first get UserReward record
        try:
            q = session.query(engagement.UserReward). \
                filter(engagement.UserReward.user_id == self._uid). \
                filter(engagement.UserReward.rewardtype == self._type)
            ur = q.one_or_none()
            if ur is None:
                ur = engagement.UserReward(user_id=self._uid, rewardtype=self._type, quantity=quantity)
                session.add(ur)
            else:
                ur.update_quantity(quantity=quantity)

            # now we need to create and/or update a Reward record
            q = session.query(engagement.Reward). \
                filter(engagement.UserReward.user_id == self._uid). \
                filter(engagement.UserReward.rewardtype == self._type). \
                filter(func.year(engagement.UserReward.created_date) == func.year(dt_now)). \
                filter(func.month(engagement.UserReward.created_date) == func.month(dt_now) ) .\
                filter(func.day(engagement.UserReward.created_date) == func.day(dt_now))
            r  = q.one_or_none()
            if r is None:
                r = engagement.Reward(user_id=self._uid, rewardtype=self._type, quantity=quantity)
                session.add(r)
            else:
                r.quantity += quantity

            return ur
        except Exception as e:
            logger.exception(msg='[rewardmgr] error making award')
            raise

    @staticmethod
    def max_reward_day(session, type: engagement.RewardType, au: usermgr.AnonUser) -> int:
        try:
            # now get the highest rewards in a day
            q = session.query(func.max(engagement.Reward.quantity)). \
                filter(engagement.Reward.user_id == au.id). \
                filter(engaement.Reward.rewardtype == type.value)
            max_score = q.one_or_none()
            if max_score is not None:
                q = session.query(engagement.Reward). \
                    filter(engagement.Reward.user_id == au.id). \
                    filter(engagement.Reward.quantity == max_score). \
                    filter(engagement.Reward.rewardtype == type.value)
                max_reward = q.first()
                return max_reward

            return None
        except Exception as e:
            raise

    @staticmethod
    def max_score_photo(session, au: usermgr.AnonUser):
        try:
            # now get the highest rated photo
            q = session.query(func.max(photo.Photo.score)). \
                filter(photo.Photo.user_id == au.id)
            highest_score = q.first()
            if highest_rated_photo is not None:
                q = session.query(photo.Photo). \
                    filter(photo.Photo.user_id == au.id). \
                    filter(photo.Photo.score == highest_score). \
                    order_by(photo.Photo.created_date.desc())
                photo = q.first()
            return photo
        except Exception as e:
            logger.exception(msg="error selecting maximum scored photo")
            raise

    @staticmethod
    def rewards(session, type: engagement.RewardType, au: usermgr.AnonUser) -> dict:
        '''
        read the user's current state of rewards
        :param session:
        :return:
        '''
        try:
            q = session.query(engagement.UserReward). \
                filter(engagement.UserReward.user_id == au.id). \
                filter(engagement.UserReward.rewardtype == type.value)
            ur = q.one_or_none()
            if ur is None: # no rewards
                return None

            max_reward = RewardManager.max_reward_day(session, type, au)
            highest_rated_photo = RewardManager.max_score_photo(session, au)

            d_rewards = {'totalLightbulbs': ur.total_balance, 'unspentBulbs': ur.current_balance}
            if max_reward is not None:
                d_rewards['mostBulbsInADay'] = max_reward.quantity
            if highest_rated_photo is not None:
                d_rewards['HighestRatedPhotoURL'] = "preview/{0}".format(highest_rated_photo.id)

            return d_rewards
        except Exception as e:
            logger.exception(msg='[rewardmgr] error reading rewards')
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


# this is the class that will orchestrate our voting. So it's job is to:
#
#  - transition categories to appropriate states
#  - set up leaderboard table for round #1
#  - create queues for round #2
#  - close voting and summarize votes
#  - any other ancillary needs of voting
#
class TallyMan():
    _redis_host = None
    _redis_port = None
    _redis_conn = None

    _orientation = None

    def leaderboard_exists(self, session, c: category.Category) -> bool:
        try:
            if self._redis_conn is None:
                sl = voting.ServerList()
                d = sl.get_redis_server(session)
                self._redis_host = d['ip']
                self._redis_port = d['port']
                self._redis_conn = redis.Redis(host=self._redis_host, port=self._redis_port)

            lbname = self.leaderboard_name(c)
            return self._redis_conn.exists(lbname)
        except Exception as e:
            logger.exception(msg='error checking if leaderboard exists')
            raise

    def change_category_state(self, session, cid: int, new_state: category.CategoryState) -> dict:
        c = category.Category.read_category_by_id(cid, session)
        if c.state == new_state:
            return {'error':error.iiServerErrors.NO_STATE_CHANGE, 'arg':None}

        c.state = new_state
        session.add(c)

        try:
            category._expiry_cache.expire_key('ALL_CATEGORIES')
        except KeyError as ke:
            pass # cache entry not created yet, ignore error

        return {'error': None, 'arg': c}

    def leaderboard_name(self, c: category.Category) -> str:
        try:
            str_lb = "leaderboard_category{0}".format(c.id)
        except Exception as e:
            logger.exception(msg='leaderboard_name(), error creating name')
            raise Exception(errno.EINVAL, 'cannot create leaderboard name')

        return str_lb

    def update_leaderboard(self, session, c: category.Category, p: photo.Photo, check_exist=True) -> None:
        '''
        update_leaderboard():
        Everytime a vote is cast, we'll update the leaderboard if it exists,
        otherwise we'll be counting on the background task to keep it up to date
        :param session: database connection
        :param c: - category
        :param p: - photo object, has score & id
        :param check_exist: =true if we should check if leaderboard exists
                            The updating of a leaderboard will create it if
                            it doesn't already exist. Leaderboard creation
                            is the sole province of the daemon that will
                            ensure leaderboards are created and populated
                            for non-voting categories in the event of a
                            Redis failure.
        :return:
        '''
        try:
            lb = self.get_leaderboard_by_category(session, c, check_exist=True)
            lb.rank_member(p.user_id, p.score, str(p.id))
        except Exception as e:
            logger.exception(msg="error updating the leaderboard")
            raise

    def get_leaderboard_by_category(self, session, c: category.Category, check_exist=True):
        '''
        this routine will return a leaderboard if it exists. Note, by
        instantiating the leaderboard object we will create a leaderboard
        entry in the Redis cache. Since leaderboard entries are created by
        a separate service, we need to check if the leaderboard exists
        via Redis directly.
        :param session:
        :param c: category we are checking for
        :return: leaderboard object, empty if leaderboard hasn't been created
        '''
        try:
            if check_exist and not self.leaderboard_exists(session, c):
                None

            lb = Leaderboard(self.leaderboard_name(c), host=self._redis_host, port=self._redis_port, page_size=10)
            return lb
        except Exception as e:
            logger.exception(msg="error getting leader board by category")
            return None

    def create_displayname(self, session, uid: int) -> str:
        u = usermgr.User.find_user_by_id(session, uid)
        if u is None:
            return "anonymous{}".format(uid)

        if u.screenname is not None:
            return u.screenname

        # if forced to use the email, don't return the domain
        ep = u.emailaddress.split('@')
        return ep[0]

    def read_thumbnail(self, session, pid: int) -> (str, photo.Photo):
        try:
            p = session.query(photo.Photo).get(pid)
            if p.active == 0: # this photo has been de-activated, it might be offensive
                return None, p

            b64_utf8 = p.read_thumbnail_b64_utf8()
            self._orientation = 1 # all thumbnails normalized to '1' orientation
            return b64_utf8, p
        except Exception as e:
            logger.exception(msg='error reading thumbnail!')
            return None, None

    def fetch_leaderboard(self, session, uid: int, c: category.Category) -> list:
        '''
        read the leaderboard object and construct a list of
        leaderboard dictionary elements for later jsonification

        Make note of the caching strategy:

            1) Cache the raw leaderboard list from the redis server for 'ttl_leaderboard' (~24 hours)
            2) cache hits on this compare with the current redis server leaderboard, if same
               then use the cached leaderboard with photos and return
            3) If NOT same, invalidate the caches (list and list w/thumbnails) and reconstruct
            4) cache all this stuff on exit

        NOTE: Could this be further optimized by realizing that leaderboards for categories that are no
              longer "voting" can be cached without all these checks as they won't change?

        :param session: database
        :param uid: user requesting leaderboard
        :param c: category for which leaderboard is request
        :return: list of of leaderboard dictionary elements or None if leaderboard doesn't exist
        '''

        if c is not None:
            logger.info(msg="retrieving leader board for category {}, \'{}\'".format(c.id, c.get_description()))
        else:
            logger.info(msg="retrieving leader board for category")

        try:
            list_key = 'LEADERBOARD{0}'.format(c.id)
            thumbnail_key = 'LEADERBOARD_THUMBNAILS{0}'.format(c.id)
            ttl_leaderboard = 60 * 60 * 24 # 24 hours
            cached_dl, cached_time = _expiry_cache.get_with_time(list_key)
            lb = self.get_leaderboard_by_category(session, c, check_exist=True)
            dl = lb.leaders(1, page_size=10, with_member_data=True)   # 1st page is top 25

            # see if the current leaderboard matches the cached leaderboard
            if cached_dl == dl and dl is not None:
                lb_list = _expiry_cache.get(thumbnail_key)
                if lb_list is not None:
                    logger.info(msg="cache hit for leaderboard{0}".format(c.id))
                    return lb_list

            _expiry_cache.put(list_key, dl, ttl=ttl_leaderboard) # 1 hour expiration of the non-photo list
            if cached_dl is not None:
                _expiry_cache.expire_key(thumbnail_key)

            lb_list = []
            for d in dl:
                lb_uid = int(str(d['member'], 'utf-8'))         # anonuser.id / userlogin.id
                try:
                    lb_pid = int(str(d['member_data'], 'utf-8'))    # photo.id
                except Exception as e:
                    continue

                lb_score = d['score']
                lb_rank = d['rank']
                if lb_uid == 0 or lb_pid == 0:  # we use a dummy value to persist leaderboard existance in daemon, filter it out
                    continue

                lb_name = self.create_displayname(session, lb_uid)
                b64_utf8, p = self.read_thumbnail(session, lb_pid) # thumbnail image as utf-8 base64
                if b64_utf8 is None:
                    continue

                lb_dict = {'username': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'orientation': self._orientation}
                lb_dict['votes'] = p.times_voted
                lb_dict['likes'] = p.likes
                if lb_uid == uid:
                    lb_dict['you'] = True
                else:
                    if usermgr.Friend.is_friend(session, uid, lb_uid):
                        lb_dict['isfriend'] = True
                    else:
                        lb_dict['isfriend'] = False

                lb_dict['image'] = b64_utf8
                lb_list.append(lb_dict)

            # Wow! That was a lot of work, so let's stuff it in the cache and use it for 5 minutes
            _expiry_cache.put(thumbnail_key, lb_list, ttl=ttl_leaderboard)
            return lb_list
        except Exception as e:
            logger.exception(msg="error fetching leaderboard")
            if c is not None:
                logger.info(msg="leaderboard error for category id ={}".format(c.id))
            else:
                logger.info(msg="leaderboard error, no category specified")
            raise

class BallotManager:
    '''
    Ballot Manager
    This class is responsible to creating our voting ballots
    '''

    _ballot = None

    def string_key_to_boolean(self, d: dict, keyname: str) -> int:
        '''
        if key is not present, return a '0'
        if key is any value other than '0', return '1'
        :param dict:
        :param keyname:
        :return: 0/1
        '''
        if keyname in d.keys():
            str_val = d[keyname]
            if str_val != '0':
                return 1
        return 0

    def tabulate_votes(self, session, uid: int, json_ballots: str) -> list:
        # we have a list of ballots, we need to determine the scoring.
        # we'll need category information:
        # category.round - to determine what score table to use
        # votinground.section - further define for round #2 what scoring to use

        # It's possible the ballotentries are from different sections, we'll
        # score based on the first ballotentry
        try:
            bid = json_ballots[0]['bid']
            be = session.query(voting.BallotEntry).get(bid)
            vr = session.query(voting.VotingRound).get(be.photo_id)
            section = 0
            if vr is not None:  # sections only matter for round 2
                section = vr.section
        except Exception as e:
            if json_ballots is not None:
                msg = 'json_ballots={}'.format(json_ballots)
            else:
                msg = "json_ballots is None!"

            logger.exception(msg=msg)
            raise

        c = session.query(category.Category).get(be.category_id)

        bel = []
        for j_be in json_ballots:
            bid = j_be['bid']
            like = self.string_key_to_boolean(j_be, 'like')
            offensive = self.string_key_to_boolean(j_be, 'offensive')

            # if there is an 'tag' specified, then create a BallotEntryTag
            # record and save it
            try:
                tags = None
                if 'tags' in j_be.keys():
                    tags = j_be['tags']
                    be_tags = voting.BallotEntryTag(bid=bid, tags=tags)
                    session.add(be_tags)
            except Exception as e:
                logger.exception(msg="error while writing ballotentrytag")
                raise

            try:
                be = session.query(voting.BallotEntry).get(bid)
                be.like = like
                be.offensive = offensive
                be.vote = j_be['vote']
                score = self.calculate_score(j_be['vote'], c.round, section)
                p = session.query(photo.Photo).get(be.photo_id)
                p.score += score
                p.times_voted += 1
                # if be.like:
                #     p.likes += 1
                bel.append(be)
            except Exception as e:
                logger.exception(msg="error while updating photo with score")
                raise

            try:
                fbm = FeedbackManager(uid=uid, pid=p.id, like=like, offensive=offensive, tags=tags)
                fbm.create_feedback(session)
            except Exception as e:
                logger.exception(msg="error while updating feedback for ballotentry")
                raise

            tm = TallyMan()
            try:
                tm.update_leaderboard(session, c, p)  # leaderboard may not be defined yet!
            except:
                pass

        return bel  # this is for testing only, no one else cares!

    def calculate_score(self, vote: int, round: int, section: int) -> int:
        if round == 0:
            score = voting._ROUND1_SCORING[0][vote - 1]
        else:
            score = voting._ROUND2_SCORING[section][vote - 1]
        return score

    def create_ballot(self, session, uid: int, c: category.Category, allow_upload=False) -> list:
        '''
        Returns a ballot list containing the photos to be voted on.

        :param session:
        :param uid:
        :param cid:
        :return: dictionary: error:<error string>
                             arg: ballots()
        '''

        # Voting Rounds are stored in the category, 0= Round #1, 1= Round #2
        pl = self.create_ballot_list(session, uid, c, allow_upload)
        self.update_votinground(session, c, pl)
        return self.add_photos_to_ballot(session, uid, c, pl)

    def update_votinground(self, session, c, plist):
        if c.round == 0:
            return

        for p in plist:
            session.query(voting.VotingRound).filter(voting.VotingRound.photo_id == p.id).update(
                {"times_voted": voting.VotingRound.times_voted + 1})
        return

    def add_photos_to_ballot(self, session, uid: int, c: category.Category, plist: list) -> voting.Ballot:

        self._ballot = voting.Ballot(c.id, uid)
        session.add(self._ballot)

        # now create the ballot entries and attach to the ballot
        for p in plist:
            be = voting.BallotEntry(user_id=p.user_id, category_id=c.id, photo_id=p.id)
            self._ballot.append_ballotentry(be)
            session.add(be)
        return self._ballot

    def read_photos_by_ballots_round2(self, session, uid: int, c: category.Category, num_votes: int,
                                      count: int) -> list:

        # *****************************
        # **** CONFIGURATION ITEMS ****
        num_sections = voting._NUM_SECTONS_ROUND2  # the "stratification" of the photos that received votes or likes
        max_votes = voting._ROUND2_TIMESVOTED  # The max # of votes we need to pick a winner
        # ****************************

        # create an array of our sections
        sl = []
        for idx in range(num_sections):
            sl.append(idx)

        bl = []
        shuffle(sl)  # randomize the section list
        oversize = count * 20
        for s in sl:
            q = session.query(photo.Photo).filter(photo.Photo.user_id != uid). \
                filter(photo.Photo.category_id == c.id). \
                filter(photo.Photo.active == 1). \
                join(voting.VotingRound, voting.VotingRound.photo_id == photo.Photo.id). \
                filter(voting.VotingRound.section == s). \
                filter(voting.VotingRound.times_voted == num_votes).limit(oversize)
            pl = q.all()
            bl.extend(pl)  # accumulate ballots we've picked, can save us time later
            # see if we encountered 4 in our journey
            if len(bl) >= count:
                return bl

        # we tried everything, let's just grab some photos from any section (HOW TO RANDOMIZE THIS??)
        if num_votes == voting._MAX_VOTING_ROUNDS:
            for s in sl:
                q = session.query(photo.Photo).filter(photo.Photo.user_id != uid). \
                    filter(photo.Photo.category_id == c.id). \
                    filter(photo.Photo.active == 1). \
                    join(voting.VotingRound, voting.VotingRound.photo_id == photo.Photo.id). \
                    filter(voting.VotingRound.section == s).limit(oversize)
                pl = q.all()
                bl.extend(pl)  # accumulate ballots we've picked, can save us time later
                if len(bl) >= count:
                    return bl
        return bl  # return what we have

    # create_ballot_list()
    # ======================
    # we will read 'count' photos from the database
    # that don't belong to this user. We loop through
    # times voted on for our first 3 passes
    #
    # if we can't get 'count' photos, then we are done
    # Round #1...
    def create_ballot_list(self, session, uid: int, c: category.Category, allow_upload: bool) -> list:
        '''

        :param session:
        :param uid: the user asking for the ballot (so we can exclude their photos)
        :param c: category
        :return: a list of '_NUM_BALLOT_ENTRIES'. We ask for more than this,
                shuffle the result and trim the list lenght, so we get some randomness
        '''
        if c.state != category.CategoryState.VOTING.value and not allow_upload:
            if c is not None:
                logger.error(msg='Category {0} for user {1} not in voting state'.format(json.dumps(c.to_json()), uid))
            raise Exception(errno.EINVAL, 'category not in VOTING state')

        # we need "count"
        count = voting._NUM_BALLOT_ENTRIES
        photos_for_ballot = []
        for num_votes in range(0, voting._MAX_VOTING_ROUNDS + 1):
            if c.round == 0:
                pl = self.read_photos_by_ballots_round1(session, uid, c, num_votes, count)
            else:
                pl = self.read_photos_by_ballots_round2(session, uid, c, num_votes, count)

            if pl is not None:
                photos_for_ballot.extend(pl)
                if len(photos_for_ballot) >= count:
                    break

        return self.cleanup_list(photos_for_ballot, count)  # remove dupes, shuffle list

    #        return photos_for_ballot[:count]

    @timeit()
    def cleanup_list(self, p4b: list, ballot_size: int) -> list:
        """
        We get a list of photos that are a straight pull from the
        database. We're going to shuffle it and not allow any
        duplicates based on 'thumb_hash'
        :param p4b:
        :param ballot_size:
        :return: list of ballots of 'ballot_size', randomized & scrubbed of duplicates (if possible)
        """

        shuffle(p4b)
        # pretty_list = []
        # for p in p4b:
        #     # we have a candidate photo, see if a copy is already in the list
        #     insert_p = True
        #     if p._photometa.thumb_hash is not None: # no hash computed, skip the check
        #         for dupe_check in pretty_list:
        #             if dupe_check._photometa.thumb_hash == p._photometa.thumb_hash:
        #                 insert_p = False
        #                 break
        #     if insert_p:
        #         pretty_list.append(p)
        #         if len(pretty_list) == ballot_size:
        #             return pretty_list

        # worst cases just return a random list
        return p4b[:ballot_size]

    def read_photos_by_ballots_round1(self, session, uid: int, c: category.Category, num_votes: int,
                                      count: int) -> list:
        '''
        read_photos_by_ballots_round1()
        read a list of photos to construct our return ballot.

        :param session:
        :param uid: user id that's voting, filter out photos that are their's
        :param c: category
        :param num_votes: select photos with this # of votes
        :param count: how many photos to fetch
        :return: list of Photo objects
        '''

        over_size = count * 20  # ask for a lot more so we can randomize a bit
        # if ballotentry has been voted on, exclude photos the user has already seen
        if num_votes == 0:
            q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
                filter(photo.Photo.active == 1). \
                filter(photo.Photo.user_id != uid). \
                filter(~exists().where(voting.BallotEntry.photo_id == photo.Photo.id)).limit(over_size)
        else:
            if num_votes == voting._MAX_VOTING_ROUNDS:
                q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
                    join(voting.BallotEntry, photo.Photo.id == voting.BallotEntry.photo_id). \
                    filter(photo.Photo.user_id != uid). \
                    filter(photo.Photo.active == 1). \
                    group_by(photo.Photo.id).limit(over_size)
            else:
                q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
                    join(voting.BallotEntry, photo.Photo.id == voting.BallotEntry.photo_id). \
                    filter(photo.Photo.user_id != uid). \
                    filter(photo.Photo.active == 1). \
                    group_by(photo.Photo.id). \
                    having(func.count(voting.BallotEntry.photo_id) == num_votes).limit(over_size)

        pl = q.all()
        return pl

    def active_voting_categories(self, session, uid: int) -> list:
        '''
        Only return categories that have photos that can be voted on
        :param session: database connection
        :param uid: user id, to filter the category list to only categories the user can access
        :return: <list> of categories available to the user for voting
        '''
        q = session.query(category.Category).filter(category.Category.state == category.CategoryState.VOTING.value). \
            join(photo.Photo, photo.Photo.category_id == category.Category.id). \
            outerjoin(event.EventCategory, event.EventCategory.category_id == category.Category.id). \
            outerjoin(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
            filter(photo.Photo.user_id != uid). \
            filter(photo.Photo.active == 1). \
            filter((event.EventUser.user_id == uid) | (event.EventUser.user_id == None)). \
            group_by(category.Category.id).having(func.count(photo.Photo.id) > 3)
        cl = q.all()

        # see if the user has uploaded to the current UPLOAD category, and if they have check to see
        # if there are enough photos include it in the vote-able category list
        q = session.query(category.Category).filter(category.Category.state == category.CategoryState.UPLOAD.value). \
            join(photo.Photo, photo.Photo.category_id == category.Category.id). \
            outerjoin(event.EventCategory, event.EventCategory.category_id == category.Category.id). \
            outerjoin(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
            filter(photo.Photo.user_id == uid). \
            filter(photo.Photo.active == 1). \
            filter((event.EventUser.user_id == uid) | (event.EventUser.user_id == None)). \
            group_by(category.Category.id).having(func.count(photo.Photo.id) > 0)
        c_can_vote_on = q.all()

        if len(c_can_vote_on) > 0:
            q = session.query(category.Category).filter(category.Category.state == category.CategoryState.UPLOAD.value). \
                join(photo.Photo, photo.Photo.category_id == category.Category.id). \
                outerjoin(event.EventCategory, event.EventCategory.category_id == category.Category.id). \
                outerjoin(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
                filter(photo.Photo.user_id != uid). \
                filter(photo.Photo.active == 1). \
                filter((event.EventUser.user_id == uid) | (event.EventUser.user_id == None)). \
                group_by(category.Category.id).having(func.count(photo.Photo.id) >= Configuration.UPLOAD_CATEGORY_PICS)
            c_upload = q.all()

            # only items in c_can_vote_on and also in c_upload can be voted on
            # so "AND" the lists
            c_voteable = set(c_can_vote_on).intersection(c_upload)
            if len(c_voteable) > 0:
                set_list = list(c_voteable)
                cl.extend(set_list)

        return cl
