from unittest import TestCase
import initschema
import datetime
from models import photo, usermgr, engagement, voting, category
from tests import DatabaseTest
import dbsetup
from sqlalchemy import func
from controllers import categorymgr, RewardMgr
import uuid

class TestEngagement(DatabaseTest):

    def test_reward_instantiation(self):
        r = engagement.Reward()
        assert(r is not None)

    def test_userreward_instantiation(self):
        ur = engagement.UserReward()
        assert(ur is not None)

    def test_cannot_decrement_reward(self):
        ur = engagement.UserReward()
        assert(not ur.decrement_quantity(quantity=1))

    def test_feedback_instantiation(self):
        fb = engagement.Feedback()
        assert(fb is not None)

    def test_feedbacktags_instantiation(self):
        ft = engagement.FeedbackTag()
        assert(ft is not None)

    def test_rewardmanager_instantiation(self):
        rm = RewardMgr.RewardManager()
        assert(rm is not None)

    def test_feedbackmanager_instantiation(self):
        fm = RewardMgr.FeedbackManager()
        assert(fm is not None)

    def get_tst_photo(self, session) -> photo.Photo:
        # get a user_id we can use for testing
        pids = session.query(func.max(photo.Photo.id)).first()
        pid = pids[0]

        p = self.session.query(photo.Photo).get(pid)
        return p

    def test_feedbackmgr_with_photo(self):
        self.setup()
        p = self.get_tst_photo(self.session)
        assert(p is not None)

        fm = RewardMgr.FeedbackManager(uid=p.user_id, pid=p.id, like=True, offensive=True, tags=['tag1', 'tag2', 'tag3'])
        assert(fm is not None)

        fm.create_feedback(self.session)
        self.session.commit()

        # read it back and do a simple check
        fb = self.session.query(engagement.Feedback).get((p.user_id, p.id))
        assert(fb is not None)
        assert(fb.like and fb.offensive)

        self.teardown()

    def create_anon_user(self, session):
        guid = str(uuid.uuid1())
        guid = guid.translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(session, guid)
        session.add(au)
        session.commit()
        return au

    def test_user_reward(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        rm = RewardMgr.RewardManager(user_id=au.id, rewardtype=engagement.RewardType.TEST)
        ur = rm.award(session, 5)
        assert(ur.current_balance == 5)
        session.commit()
        session.close()
        self.teardown()

    def test_user_increment_reward(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        rm = RewardMgr.RewardManager(user_id=au.id, rewardtype=engagement.RewardType.TEST)
        ur = rm.award(session, engagement._REWARDS['amount'][engagement.RewardType.TEST])
        assert(ur.current_balance == engagement._REWARDS['amount'][engagement.RewardType.TEST])
        session.commit()

        # now a second update
        ur2 = rm.award(session, engagement._REWARDS['amount'][engagement.RewardType.TEST])
        assert(ur2.current_balance == engagement._REWARDS['amount'][engagement.RewardType.TEST] + engagement._REWARDS['amount'][engagement.RewardType.TEST])

        session.commit()
        session.close()
        self.teardown()

    def test_user_spend_reward(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        rm = RewardMgr.RewardManager(user_id=au.id, rewardtype=engagement.RewardType.TEST)
        ur = rm.award(session, engagement._REWARDS['amount'][engagement.RewardType.TEST])
        assert(ur.current_balance == engagement._REWARDS['amount'][engagement.RewardType.TEST])
        session.commit()

        # now a second update
        ur2 = rm.award(session, engagement._REWARDS['amount'][engagement.RewardType.TEST])
        assert(ur2.current_balance == engagement._REWARDS['amount'][engagement.RewardType.TEST]*2)
        assert(ur2.total_balance == engagement._REWARDS['amount'][engagement.RewardType.TEST]*2)

        # now a second update
        ur2 = rm.spend(session, 10)
        assert(ur2.current_balance == engagement._REWARDS['amount'][engagement.RewardType.TEST]*2 - 10)
        assert(ur2.total_balance == engagement._REWARDS['amount'][engagement.RewardType.TEST]*2)

        session.commit()
        session.close()
        self.teardown()

    def test_rewardtype_strings(self):
        assert(str(engagement.RewardType.LIGHTBULB) == 'LIGHTBULB')
        assert(str(engagement.RewardType.TEST) == 'TEST')

    def test_consecutive_not_voting_days(self):
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        isConsecutive = RewardMgr.RewardManager.consecutive_voting_days(session, au, 5)
        assert(not isConsecutive)

    def test_consecutive_voting_days(self):
        session = dbsetup.Session()
        au = self.create_anon_user(session)

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()

        # need to create some ballots
        day_span = 5
        dt_now = datetime.datetime.now()
        dt_start = dt_now - datetime.timedelta(days=day_span)
        dt = dt_start
        for i in range(0, day_span+1):
            b = voting.Ballot(uid=au.id, cid=c.id)
            b.created_date = dt
            session.add(b)
            dt += datetime.timedelta(days=1)

        session.commit()

        # now see if we have consecutive days
        isConsecutive = RewardMgr.RewardManager.consecutive_voting_days(session, au, day_span=day_span)
        assert(isConsecutive)

    def test_consecutive_voting_days_multiple_votes_per_day(self):
        session = dbsetup.Session()
        au = self.create_anon_user(session)

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()

        # need to create some ballots
        day_span = 30
        dt_now = datetime.datetime.now()
        hour_span = day_span * 24
        dt = dt_now - datetime.timedelta(days=day_span)
        for i in range(0, day_span*2+1):
            b = voting.Ballot(uid=au.id, cid=c.id)
            b.created_date = dt
            session.add(b)
            dt += datetime.timedelta(hours=12)

        session.commit()

        # now see if we have consecutive days
        isConsecutive = RewardMgr.RewardManager.consecutive_voting_days(session, au, day_span=day_span)
        assert(isConsecutive)

        isConsecutive = RewardMgr.RewardManager.consecutive_voting_days(session, au, day_span=day_span+1)
        assert(not isConsecutive)

    def test_consecutive_day_oneshot(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()

        # need to create some ballots
        day_span = 30
        dt_now = datetime.datetime.now()
        hour_span = day_span * 24
        dt = dt_now - datetime.timedelta(days=day_span)
        for i in range(0, day_span*2+1):
            b = voting.Ballot(uid=au.id, cid=c.id)
            b.created_date = dt
            session.add(b)
            dt += datetime.timedelta(hours=12)

        session.commit()

        # now see if we have consecutive days
        RewardMgr.RewardManager(user_id=au.id, rewardtype=engagement.RewardType.DAYSPLAYED_30).check_consecutive_day_rewards(session, au, engagement.RewardType.DAYSPLAYED_30)
        session.commit()
        q = session.query(engagement.UserReward). \
            filter(engagement.UserReward.rewardtype == str(engagement.RewardType.DAYSPLAYED_30) ). \
            filter(engagement.UserReward.user_id == au.id)
        ur = q.one_or_none()
        assert(ur is not None)

        d_rewards = RewardMgr.RewardManager.rewards(session, engagement.RewardType.LIGHTBULB, au)
        assert(d_rewards is not None)
        assert(d_rewards['vote30'])
        assert(not d_rewards['vote100'])
        assert(not d_rewards['upload7'])
        assert(not d_rewards['upload30'])
        assert(not d_rewards['upload100'])

        self.teardown()

    def test_highest_rated_photo_none(self):

        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        assert(au is not None)

        ph = RewardMgr.RewardManager.max_score_photo(session, au)
        assert(ph is None)
        self.teardown()

    def test_highest_rated_photo(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        assert(au is not None)

        # create a category we can test in
        category_description = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()

        # now create photo & photometa data records
        pl = []
        for i in range(0,10):
            p = photo.Photo()
            pm = photo.PhotoMeta(height=0, width=0, th_hash=None)
            p.user_id = au.id
            p.category_id = c.id
            p.filepath = 'boguspath'
            p.filename = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
            p.likes = 0
            p.score = i
            p.active = 1
            p._photometa = pm
            session.add(p)
            pl.append(p)

        session.commit()

        # now ask for the high scored photo
        p = RewardMgr.RewardManager.max_score_photo(session, au)
        assert(p is not None)
        assert(p.score == i)

        d_rewards = RewardMgr.RewardManager.rewards(session, engagement.RewardType.LIGHTBULB, au)
        assert(d_rewards is not None)
        assert(d_rewards['HighestRatedPhotoURL'] is not None)
        assert(not d_rewards['vote30'])
        assert(not d_rewards['vote100'])
        assert(not d_rewards['upload7'])
        assert(not d_rewards['upload30'])
        assert(not d_rewards['upload100'])

        self.teardown()

    def test_consecutive_7day_photo(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        assert(au is not None)

        # create a category we can test in
        category_description = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()

        # now create photo & photometa data records
        pl = []
        day_span = 7
        dt_now = datetime.datetime.now()
        dt_start = dt_now - datetime.timedelta(days=day_span)
        dt = dt_start
        for i in range(0, day_span+1):
            p = photo.Photo()
            p.created_date = dt
            pm = photo.PhotoMeta(height=0, width=0, th_hash=None)
            pm.created_date = dt
            p.user_id = au.id
            p.category_id = c.id
            p.filepath = 'boguspath'
            p.filename = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
            p.likes = 0
            p.score = i
            p.active = 1
            p._photometa = pm
            session.add(p)
            pl.append(p)
            dt += datetime.timedelta(days=1)

        session.commit()

        RewardMgr.RewardManager().update_rewards_for_photo(session, au)

        # now ask for the high scored photo
        p = RewardMgr.RewardManager.max_score_photo(session, au)
        assert(p is not None)
        assert(p.score == i)

        d_rewards = RewardMgr.RewardManager.rewards(session, engagement.RewardType.LIGHTBULB, au)
        assert(d_rewards is not None)
        assert(d_rewards['HighestRatedPhotoURL'] is not None)
        assert(not d_rewards['vote30'])
        assert(not d_rewards['vote100'])
        assert(d_rewards['firstphoto'])
        assert(d_rewards['upload7'])
        assert(not d_rewards['upload30'])
        assert(not d_rewards['upload100'])
        assert(d_rewards['totalLightbulbs'] == engagement._REWARDS['amount'][engagement.RewardType.FIRSTPHOTO] + engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_7])
        assert(d_rewards['unspentBulbs'] == engagement._REWARDS['amount'][engagement.RewardType.FIRSTPHOTO] + engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_7])

        self.teardown()

    def test_consecutive_30day_photo(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        assert(au is not None)

        # create a category we can test in
        category_description = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()

        # now create photo & photometa data records
        pl = []
        day_span = 30
        dt_now = datetime.datetime.now()
        dt_start = dt_now - datetime.timedelta(days=day_span)
        dt = dt_start
        for i in range(0, day_span+1):
            p = photo.Photo()
            p.created_date = dt
            pm = photo.PhotoMeta(height=0, width=0, th_hash=None)
            pm.created_date = dt
            p.user_id = au.id
            p.category_id = c.id
            p.filepath = 'boguspath'
            p.filename = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
            p.likes = 0
            p.score = i
            p.active = 1
            p._photometa = pm
            session.add(p)
            pl.append(p)
            dt += datetime.timedelta(days=1)

        session.commit()

        RewardMgr.RewardManager().update_rewards_for_photo(session, au)

        # now ask for the high scored photo
        p = RewardMgr.RewardManager.max_score_photo(session, au)
        assert(p is not None)
        assert(p.score == i)

        d_rewards = RewardMgr.RewardManager.rewards(session, engagement.RewardType.LIGHTBULB, au)
        assert(d_rewards is not None)
        assert(d_rewards['HighestRatedPhotoURL'] is not None)
        assert(not d_rewards['vote30'])
        assert(not d_rewards['vote100'])
        assert(d_rewards['firstphoto'])
        assert(d_rewards['upload7'])
        assert(d_rewards['upload30'])
        assert(not d_rewards['upload100'])
        assert(d_rewards['totalLightbulbs'] == engagement._REWARDS['amount'][engagement.RewardType.FIRSTPHOTO] + engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_7]+engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_30])
        assert(d_rewards['unspentBulbs'] == engagement._REWARDS['amount'][engagement.RewardType.FIRSTPHOTO] + engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_7]+ engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_30])

        self.teardown()

    def test_consecutive_100day_photo(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        assert(au is not None)

        # create a category we can test in
        category_description = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()

        # now create photo & photometa data records
        pl = []
        day_span = 100
        dt_now = datetime.datetime.now()
        dt_start = dt_now - datetime.timedelta(days=day_span)
        dt = dt_start
        for i in range(0, day_span+1):
            p = photo.Photo()
            p.created_date = dt
            pm = photo.PhotoMeta(height=0, width=0, th_hash=None)
            pm.created_date = dt
            p.user_id = au.id
            p.category_id = c.id
            p.filepath = 'boguspath'
            p.filename = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
            p.likes = 0
            p.score = i
            p.active = 1
            p._photometa = pm
            session.add(p)
            pl.append(p)
            dt += datetime.timedelta(days=1)

        session.commit()

        RewardMgr.RewardManager().update_rewards_for_photo(session, au)

        # now ask for the high scored photo
        p = RewardMgr.RewardManager.max_score_photo(session, au)
        assert(p is not None)
        assert(p.score == i)

        d_rewards = RewardMgr.RewardManager.rewards(session, engagement.RewardType.LIGHTBULB, au)
        assert(d_rewards is not None)
        assert(d_rewards['HighestRatedPhotoURL'] is not None)
        assert(not d_rewards['vote30'])
        assert(not d_rewards['vote100'])
        assert(d_rewards['firstphoto'])
        assert(d_rewards['upload7'])
        assert(d_rewards['upload30'])
        assert(d_rewards['upload100'])
        assert(d_rewards['totalLightbulbs'] == engagement._REWARDS['amount'][engagement.RewardType.FIRSTPHOTO] + engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_7]+engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_30]+engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_100])
        assert(d_rewards['unspentBulbs'] == engagement._REWARDS['amount'][engagement.RewardType.FIRSTPHOTO] + engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_7]+ engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_30]+ engagement._REWARDS['amount'][engagement.RewardType.DAYSPHOTO_100])

        self.teardown()