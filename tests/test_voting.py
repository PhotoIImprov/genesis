from unittest import TestCase
import initschema
import datetime
import os, errno
import uuid
from models import resources
from models import category, photo, usermgr, voting
from tests import DatabaseTest
from models import voting
from models import error

class TestVoting(DatabaseTest):

    def test_create_ballot_list_ROUND2_noargs(self):
        bm = voting.BallotManager()
        d = bm.create_ballot_list_ROUND2(None, None, None, 4)
        assert(d is None)

    def test_calculate_score_round2(self):
        bm = voting.BallotManager()

        score = bm.calculate_score(1, 1, 0) # first pick of first secton
        assert(score == 7)
        score = bm.calculate_score(1,1,1)
        assert(score == 6)
        score = bm.calculate_score(1,1,2)
        assert(score == 5)
        score = bm.calculate_score(1,1,3)
        assert(score == 4)

    def test_create_ballot_list_ROUND1_noargs(self):
        bm = voting.BallotManager()

        try:
            d = bm.create_ballot_list_ROUND1(None, None, None, 4)
            assert(False)
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)

    def test_create_ballot_list_ROUND1_bad_category(self):
        self.setup()
        bm = voting.BallotManager()

        d = bm.create_ballot_list_ROUND1(self.session, 1, 0, 4)
    #    assert(d[error] is not None)

    def test_read_photos_not_balloted_noargs(self):
        self.setup()
        bm = voting.BallotManager()

        try:
            bm.read_photos_not_balloted(None, None, None, 4)
            assert(False)
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)

    def test_votinground_init(self):
        vr = voting.VotingRound(photo_id=1)
        assert(vr.photo_id == 1)

    def test_read_photo_by_votes_noargs(self):
        bm = voting.BallotManager()
        try:
            bm.read_photos_not_balloted(None, None, None, 4)
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)
            return

        assert(False) # should never get here...

    def test_read_thumbnail_fakepid(self):
        self.setup()
        tm = voting.TallyMan()

        th = tm.read_thumbnail(self.session, 0)
        assert(th == None)

    def test_create_leaderboard_nocid(self):
        tm = voting.TallyMan()
        r = tm.create_leaderboard(1, 1, None)
        assert(r == None)

    def test_create_displayname_anonymous(self):
        tm = voting.TallyMan()
        self.setup()
        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        self.session.commit()
        name = tm.create_displayname(self.session, au.id)

        assert(name == 'anonymous{}'.format(au.id))
