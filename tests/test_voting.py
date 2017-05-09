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

    def test_votinground_init(self):
        vr = voting.VotingRound(photo_id=1)
        assert(vr.photo_id == 1)

    def test_read_thumbnail_fakepid(self):
        self.setup()
        tm = voting.TallyMan()

        th = tm.read_thumbnail(self.session, 0)
        assert(th == None)

    def test_create_leaderboard_nocid(self):
        self.setup()
        tm = voting.TallyMan()
        try:
            r = tm.create_leaderboard(self.session, 1, None)
        except Exception as e:
            assert(e.args[0] == errno.EINVAL and e.args[1] == 'cannot create leaderboard name')
            return

        assert(False)

    def test_create_displayname_anonymous(self):
        tm = voting.TallyMan()
        self.setup()
        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        self.session.commit()
        name = tm.create_displayname(self.session, au.id)

        assert(name == 'anonymous{}'.format(au.id))
