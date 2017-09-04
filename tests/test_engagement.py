from unittest import TestCase
import initschema
import datetime
import os, errno
from models import photo, usermgr, engagement
from tests import DatabaseTest
from sqlalchemy import func
import dbsetup
import iiServer
from flask import Flask
from sqlalchemy import func
from controllers import categorymgr


class TestEngagement(DatabaseTest):

    def test_reward_instantiation(self):
        r = engagement.Reward()
        assert(r is not None)

    def test_userreward_instantiation(self):
        ur = engagement.UserReward()
        assert(ur is not None)

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