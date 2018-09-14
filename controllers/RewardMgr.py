"""the controller for the event model. """
import errno
from datetime import timedelta, datetime
from sqlalchemy import func
import redis
from leaderboard.leaderboard import Leaderboard
from logsetup import logger, timeit
from cache.ExpiryCache import _expiry_cache
from models import error
from models import usermgr, category, engagement, photo, voting


# --- RewardManager ---
class RewardManager():
    _user_id = None
    _rewardtype = None

    def __init__(self, **kwargs):
        self._user_id = kwargs.get('user_id', None)
        self._rewardtype = kwargs.get('rewardtype', None)
        if self._rewardtype is not None:
            assert isinstance(self._rewardtype, engagement.RewardType)

    def create_reward(self, session, quantity: int) -> None:
        try:
            r = engagement\
                .Reward(user_id=self._user_id, rewardtype=self._rewardtype, quantity=quantity)
            session.add(r)

            ur_l = session.query(engagement.UserReward)\
                .filter(engagement.UserReward.user_id == self._user_id)\
                .filter(engagement.UserReward.rewardtype == str(self._rewardtype) )\
                .all()
            if ur_l is not None and len(ur_l) > 0:
                ur = ur_l[0]
            else:
                ur = engagement\
                    .UserReward(user_id=self._user_id, rewardtype=self._rewardtype, quantity=0)

            ur.update_quantity(quantity)
            session.add(ur)
        except Exception as e:
            logger.exception(msg="error updating reward quantity")
            raise

    def spend(self, session, quantity: int) -> engagement.UserReward:
        try:
            q = session.query(engagement.UserReward). \
                filter(engagement.UserReward.user_id == self._user_id). \
                filter(engagement.UserReward.rewardtype == str(engagement.RewardType.LIGHTBULB) )
            ur = q.one()

            if not ur.decrement_quantity(quantity=quantity):
                raise Exception('insufficient awards', ur.current_balance)
            return ur
        except Exception as e:
            logger.exception(msg='[rewardmgr] error making award')
            raise

    def update_quantity(self, session, quantity: int, rewardtype: engagement.RewardType) -> engagement.UserReward:
        try:
            q = session.query(engagement.UserReward). \
                filter(engagement.UserReward.user_id == self._user_id). \
                filter(engagement.UserReward.rewardtype == str(rewardtype))
            ur = q.one_or_none()
            if ur is None:
                ur = engagement.UserReward(user_id=self._user_id, rewardtype=rewardtype, quantity=quantity)
                session.add(ur)
            else:
                ur.update_quantity(quantity=quantity)

            return ur
        except Exception as e:
            raise

    def award(self, session, quantity: int, dt_now = datetime.now()) -> engagement.UserReward:
        # first get UserReward record
        try:
            q = session.query(engagement.UserReward). \
                filter(engagement.UserReward.user_id == self._user_id). \
                filter(engagement.UserReward.rewardtype == str(self._rewardtype) )
            ur = q.one_or_none()
            if ur is None:
                ur = engagement.UserReward(user_id=self._user_id, rewardtype=self._rewardtype, quantity=quantity)
                session.add(ur)

            # now we need to create and/or update a Reward record
            q = session.query(engagement.Reward). \
                filter(engagement.Reward.user_id == self._user_id). \
                filter(engagement.Reward.rewardtype == str(engagement.RewardType.LIGHTBULB) ). \
                filter(func.year(engagement.Reward.created_date) == func.year(dt_now)). \
                filter(func.month(engagement.Reward.created_date) == func.month(dt_now) ) .\
                filter(func.day(engagement.Reward.created_date) == func.day(dt_now))
            r  = q.one_or_none()
            if r is None:
                r = engagement.Reward(user_id=self._user_id, rewardtype=engagement.RewardType.LIGHTBULB, quantity=quantity)
                session.add(r)
            else:
                r.quantity += quantity

            ur = self.update_quantity(session, quantity=quantity, rewardtype=engagement.RewardType.LIGHTBULB)
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
                filter(engagement.Reward.rewardtype == str(type) )
            max_score = q.scalar()
            if max_score is not None:
                q = session.query(engagement.Reward). \
                    filter(engagement.Reward.user_id == au.id). \
                    filter(engagement.Reward.quantity == max_score). \
                    filter(engagement.Reward.rewardtype == str(type))
                max_reward = q.first()
                return max_reward

            return None
        except Exception as e:
            raise

    @staticmethod
    def max_score_photo(session, au: usermgr.AnonUser) -> photo.Photo:
        try:
            # now get the highest rated photo
            q = session.query(func.max(photo.Photo.score)). \
                filter(photo.Photo.user_id == au.id)
            highest_score = q.scalar()
            if highest_score is None:
                return None
            q = session.query(photo.Photo). \
                filter(photo.Photo.user_id == au.id). \
                filter(photo.Photo.score == highest_score). \
                order_by(photo.Photo.created_date.desc())
            ph = q.first()
            return ph
        except Exception as e:
            logger.exception(msg="error selecting maximum scored photo")
            raise

    @staticmethod
    def add_reward_types(ur_l: list, d: dict) -> dict:
        voted_30 = False
        voted_100 = False
        upload_7 = False
        upload_30 = False
        upload_100 = False
        first_photo = False
        for ur in ur_l:
            if ur.rewardtype == str(engagement.RewardType.DAYSPLAYED_30):
                voted_30 = True
            elif ur.rewardtype == str(engagement.RewardType.DAYSPLAYED_100):
                voted_100 = True
            elif ur.rewardtype == str(engagement.RewardType.DAYSPHOTO_7):
                upload_7 = True
            elif ur.rewardtype == str(engagement.RewardType.DAYSPHOTO_30):
                upload_30 = True
            elif ur.rewardtype == str(engagement.RewardType.DAYSPHOTO_100):
                upload_100 = True
            elif ur.rewardtype == str(engagement.RewardType.FIRSTPHOTO):
                first_photo = True

        d['vote30'] = voted_30
        d['vote100'] = voted_100
        d['upload7'] = upload_7
        d['upload30'] = upload_30
        d['upload100'] = upload_100
        d['firstphoto'] = first_photo
        return d

    @staticmethod
    def rewards(session, type: engagement.RewardType, au: usermgr.AnonUser) -> dict:
        """
        read the user's current state of rewards
        :param session:
        :return:
        """
        d_rewards = {}
        try:
            highest_rated_photo = RewardManager.max_score_photo(session, au)
            if highest_rated_photo is not None:
                d_rewards['HighestRatedPhotoURL'] = "preview/{0}".format(highest_rated_photo.id)

            q = session.query(engagement.UserReward). \
                filter(engagement.UserReward.user_id == au.id)
            ur_l = q.all()
            if ur_l is not None:
                for ur in ur_l:
                    total_bulbs = 0
                    current_bulbs = 0
                    if ur.rewardtype == str(engagement.RewardType.LIGHTBULB):
                        total_bulbs = ur.total_balance
                        current_bulbs = ur.current_balance
                    d_rewards['totalLightbulbs'] = total_bulbs
                    d_rewards['unspentBulbs'] = current_bulbs

                max_reward = RewardManager.max_reward_day(session, type, au)
                if max_reward is not None:
                    d_rewards['mostBulbsInADay'] = max_reward.quantity
                else:
                    d_rewards['mostBulbsInADay'] = 0

                d_rewards = RewardManager.add_reward_types(ur_l, d_rewards)

            if len(d_rewards) == 0:
                return None
            return d_rewards
        except Exception as e:
            logger.exception(msg='[rewardmgr] error reading rewards')
            raise

    def check_consecutive_day_rewards(self, session, au: usermgr.AnonUser, rewardtype: engagement.RewardType):
        # check our 'consecutive day' awards, pull out specifics from dictionary
        award_qty = engagement._REWARDS['amount'][rewardtype] # how many "lightbulbs" to award
        day_span = engagement._REWARDS['span'][rewardtype]  # how many consecutive days of play
        try:
            q = session.query(engagement.UserReward).\
                filter(engagement.UserReward.rewardtype == str(rewardtype) ) .\
                filter(engagement.UserReward.user_id == au.id)
            ur = q.one_or_none()
            if ur is None:
                if RewardManager.consecutive_voting_days(session, au, day_span=day_span):
                     # create a xx-days of consecutive play award
                    self.award(session, quantity=award_qty)
                    return
        except Exception as e:
            raise

    @staticmethod
    def consecutive_voting_days(session, au: usermgr.AnonUser, day_span: int) -> bool:
        """
        given a span-of-days, will determine if the user has been voting consistently for that
        period of time and return 'True' if so.
        :param session:
        :param au:
        :param day_span:
        :return:
        """
        try:
            dt_now = datetime.now()
            early_date = dt_now - timedelta(hours=day_span*24 + 1)

            # group by the YYYY-MM-DD and count the records some our starting date, it should match 'day-span' if we've been consistently voting
            q = session.query(func.year(voting.Ballot.created_date), func.month(voting.Ballot.created_date), func.day(voting.Ballot.created_date)). \
                filter(voting.Ballot.user_id == au.id). \
                filter(voting.Ballot.created_date >= early_date). \
                distinct(func.year(voting.Ballot.created_date), \
                         func.month(voting.Ballot.created_date), \
                         func.day(voting.Ballot.created_date) )
            d = q.all()
            return len(d) >= day_span+1 # picket fence
        except Exception as e:
            raise

    def check_consecutive_photo_day_rewards(self, session, au: usermgr.AnonUser, rewardtype: engagement.RewardType):
        """
        consecutive voting rewards are only awarded once, we track their state in the UserReward
        table, so before we incure the cost of the consecutive check query, do the quick check to
        see if the reward has already been issued.
        :param session:
        :param au:
        :param rewardtype:
        :return:
        """
        award_qty = engagement._REWARDS['amount'][rewardtype] # how many "lightbulbs" to award
        day_span = engagement._REWARDS['span'][rewardtype]  # how many consecutive days of play
        self._rewardtype = rewardtype
        try:
            q = session.query(engagement.UserReward).\
                filter(engagement.UserReward.rewardtype == str(rewardtype)).\
                filter(engagement.UserReward.user_id == au.id)
            ur = q.one_or_none()
            if ur is None:
                if RewardManager.consecutive_photo_days(session, au, day_span=day_span):
                     # create a xx-days of consecutive photo upload award
                    self.award(session, quantity=award_qty)
                    return
        except Exception as e:
            raise

    @staticmethod
    def consecutive_photo_days(session, au: usermgr.AnonUser, day_span: int) -> bool:
        """
        check if the user has submitted a photo every day for a the specified span-of-days
        :param session:
        :param au:
        :param day_span:
        :return:
        """
        try:
            dt_now = datetime.now()
            early_date = dt_now - timedelta(hours=day_span*24 + 1)

            # group by YYYY-MM-DD and check that there's a record for every day since the start of this period
            q = session.query(func.year(photo.PhotoMeta.created_date), func.month(photo.PhotoMeta.created_date), func.day(photo.PhotoMeta.created_date)). \
                join(photo.Photo, photo.Photo.id == photo.PhotoMeta.id). \
                filter(photo.Photo.user_id == au.id). \
                filter(photo.PhotoMeta.created_date >= early_date). \
                distinct(func.year(photo.PhotoMeta.created_date), \
                         func.month(photo.PhotoMeta.created_date), \
                         func.day(photo.PhotoMeta.created_date) )
            d = q.all()
            return len(d) >= day_span+1 # picket fence
        except Exception as e:
            raise

    def first_photo(self, session, au: usermgr.AnonUser) -> None:
        try:
            q = session.query(engagement.UserReward). \
                filter(engagement.UserReward.user_id == au.id). \
                filter(engagement.UserReward.rewardtype == str(engagement.RewardType.FIRSTPHOTO))

            ur = q.one_or_none()
            if ur is None:
                self._rewardtype = engagement.RewardType.FIRSTPHOTO
                self._user_id = au.id
                self.award(session, quantity=engagement._REWARDS['amount'][engagement.RewardType.FIRSTPHOTO])
        except Exception as e:
            raise

    def update_rewards_for_photo(self, session, au: usermgr.AnonUser) -> None:
        """
        Update the rewards for photo uploading activity
        :param session:
        :param uid:
        :return:
        """
        # check out consecutive days of play...from
        try:
            self.first_photo(session, au)
            self.check_consecutive_photo_day_rewards(session, au, rewardtype=engagement.RewardType.DAYSPHOTO_7)
            self.check_consecutive_photo_day_rewards(session, au, rewardtype=engagement.RewardType.DAYSPHOTO_30)
            self.check_consecutive_photo_day_rewards(session, au, rewardtype=engagement.RewardType.DAYSPHOTO_100)
        except Exception as e:
            raise
        return None


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
        """
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
        """
        try:
            lb = self.get_leaderboard_by_category(session, c, check_exist=True)
            lb.rank_member(p.id, p.score, str(p.user_id))
        except Exception as e:
            logger.exception(msg="error updating the leaderboard")
            raise

    def get_leaderboard_by_category(self, session, c: category.Category, check_exist=True):
        """
        this routine will return a leaderboard if it exists. Note, by
        instantiating the leaderboard object we will create a leaderboard
        entry in the Redis cache. Since leaderboard entries are created by
        a separate service, we need to check if the leaderboard exists
        via Redis directly.
        :param session:
        :param c: category we are checking for
        :param check_exist - check if the leaderboard exists
        :return: leaderboard object, empty if leaderboard hasn't been created
        """
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

    def fetch_leaderboard(self, session, au: usermgr.AnonUser, c: category.Category) -> list:
        """
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
        :param au: user requesting leaderboard
        :param c: category for which leaderboard is request
        :return: list of of leaderboard dictionary elements or None if leaderboard doesn't exist
        """

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
                    logger.info(msg="cache hit for leaderboard, category_id ={0}".format(c.id))
                    return lb_list

            _expiry_cache.put(list_key, dl, ttl=ttl_leaderboard) # 1 hour expiration of the non-photo list
            if cached_dl is not None:
                _expiry_cache.expire_key(thumbnail_key)

            lb_list = []
            for d in dl:
                lb_pid = int(str(d['member'], 'utf-8'))     # photo.id
                try:
                    lb_uid = int(str(d['member_data'], 'utf-8')) # anonuser.id / userlogin.id
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

                lb_dict = {'username': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'orientation': self._orientation, 'pid': lb_pid}
                lb_dict['votes'] = p.times_voted
                lb_dict['likes'] = p.likes
                if lb_uid == au.id:
                    lb_dict['you'] = True
                else:
                    lb_dict['isfriend'] = usermgr.Friend.is_friend(session, au.id, lb_uid)

                lb_dict['image'] = b64_utf8
                lb_list.append(lb_dict)

            # Wow! That was a lot of work, so let's stuff it in the cache and use it for 5 minutes
            _expiry_cache.put(thumbnail_key, lb_list, ttl=ttl_leaderboard)
            logger.info(msg="[fetch_leaderboard]caching leaderboard for category #{0}".format(c.id))
            return lb_list
        except Exception as e:
            logger.exception(msg="error fetching leaderboard")
            if c is not None:
                logger.info(msg="leaderboard error for category id ={}".format(c.id))
            else:
                logger.info(msg="leaderboard error, no category specified")
            raise
