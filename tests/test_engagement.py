from unittest import TestCase
import initschema
import datetime
import os, errno
from models import photo, usermgr, engagement, voting, category
from tests import DatabaseTest
from sqlalchemy import func
import dbsetup
import iiServer
from flask import Flask
from sqlalchemy import func
from controllers import categorymgr
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
        rm = categorymgr.RewardManager()
        assert(rm is not None)

    def test_feedbackmanager_instantiation(self):
        fm = categorymgr.FeedbackManager()
        assert(fm is not None)

    def get_test_photo(self, session) -> photo.Photo:
        # get a user_id we can use for testing
        pids = session.query(func.max(photo.Photo.id)).first()
        pid = pids[0]

        p = self.session.query(photo.Photo).get(pid)
        return p

    def test_feedbackmgr_with_photo(self):
        self.setup()
        p = self.get_test_photo(self.session)
        assert(p is not None)

        fm = categorymgr.FeedbackManager(uid=p.user_id, pid=p.id, like=True, offensive=True, tags=['tag1', 'tag2', 'tag3'])
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
        rm = categorymgr.RewardManager(user_id=au.id, rewardtype=engagement.RewardType.TEST.value)
        ur = rm.award(session, 5)
        assert(ur.current_balance == 5)
        session.commit()
        session.close()
        self.teardown()

    def test_user_increment_reward(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        rm = categorymgr.RewardManager(user_id=au.id, rewardtype=engagement.RewardType.TEST.value)
        ur = rm.award(session, 5)
        assert(ur.current_balance == 5)
        session.commit()

        # now a second update
        ur2 = rm.award(session, 10)
        assert(ur2.current_balance == 15)
        session.commit()
        session.close()
        self.teardown()

    def test_user_spend_reward(self):
        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        rm = categorymgr.RewardManager(user_id=au.id, rewardtype=engagement.RewardType.TEST.value)
        ur = rm.award(session, 5)
        assert(ur.current_balance == 5)
        session.commit()

        # now a second update
        ur2 = rm.award(session, 10)
        assert(ur2.current_balance == 15)
        assert(ur2.total_balance == 15)

        # now a second update
        ur2 = rm.spend(session, 10)
        assert(ur2.current_balance == 5)
        assert(ur2.total_balance == 15)

        session.commit()
        session.close()
        self.teardown()

    def test_rewardtype_strings(self):

        assert(engagement.RewardType.to_str(engagement.RewardType.LIGHTBULB.value) == 'LIGHTBULB')
        assert(engagement.RewardType.to_str(engagement.RewardType.TEST.value) == 'TEST')
        assert(engagement.RewardType.to_str(2) == 'UNKNOWN')

    def test_consecutive_not_voting_days(self):
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        isConsecutive = categorymgr.RewardManager.consecutive_voting_days(session, au, 5)
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
        isConsecutive = categorymgr.RewardManager.consecutive_voting_days(session, au, day_span=day_span)
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
        isConsecutive = categorymgr.RewardManager.consecutive_voting_days(session, au, day_span=day_span)
        assert(isConsecutive)

        # isConsecutive = categorymgr.RewardManager.consecutive_voting_days(session, au, day_span=day_span-1)
        # assert(not isConsecutive)

        isConsecutive = categorymgr.RewardManager.consecutive_voting_days(session, au, day_span=day_span+1)
        assert(not isConsecutive)

    def test_highest_rated_photo_none(self):

        self.setup()
        session = dbsetup.Session()
        au = self.create_anon_user(session)
        assert(au is not None)

        ph = categorymgr.RewardManager.max_score_photo(session, au)
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

        # now ask for the hight score
        p = categorymgr.RewardManager.max_score_photo(session, au)
        assert(p is not None)
        assert(p.score == i)

        d_rewards = categorymgr.RewardManager.rewards(session, engagement.RewardType.LIGHTBULB, au)
        assert(d_rewards is not None)
        assert(d_rewards['HighestRatedPhotoURL'] is not None)

        self.teardown()