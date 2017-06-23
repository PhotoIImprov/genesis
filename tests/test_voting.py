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
from sqlalchemy import func
from handlers import dbg_handler
from logsetup import logger

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
            r = tm.fetch_leaderboard(self.session, 1, None)
        except Exception as e:
#            assert(e.args[0] == errno.EINVAL and e.args[1] == 'cannot create leaderboard name')
            return

        assert(False)

    def test_leaderboard_member(self):
        self.setup()
        tm = voting.TallyMan()
        c = category.Category()
        c.id = 87654321

        if not tm.leaderboard_exists(self.session, c):
            lb = tm.get_leaderboard_by_category(self.session, c, check_exist=True)
            lb.delete_leaderboard()

        lb = tm.get_leaderboard_by_category(self.session, c, check_exist=False)
        assert(lb is not None)

        # we have a leaderboard for this category, create an empty key
        lb.rank_member('0', 0, '0') # member, score, member_data
        try:
            d = tm.fetch_leaderboard(self.session, 1, c)
            assert(d is not None)
        except Exception as e:
            assert(False)


    def test_create_displayname_anonymous(self):
        tm = voting.TallyMan()
        self.setup()
        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        self.session.flush()
        name = tm.create_displayname(self.session, au.id)

        assert(name == 'anonymous{}'.format(au.id))

    def create_category(self):
        # first we need a resource
        max_resource_id = self.session.query(func.max(resources.Resource.resource_id)).one()
        rid = max_resource_id[0] + 1
        r = resources.Resource.create_resource(rid, 'EN', 'round 2 testing')
        resources.Resource.write_resource(self.session, r)
        self.session.commit()

        # now create our category & the image indexer
        s_date = datetime.datetime.now()
        e_date =  s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date, category.CategoryState.UPLOAD)
        self.session.add(c)
        self.session.flush()
        return c

    def create_user(self):
        # create a user
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})

        au = usermgr.AnonUser.create_anon_user(self.session, guid)
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, '{}@gmail.com'.format(guid), 'pa55w0rd')

        return u

    def upload_image(self, pi, c, u):
        fo = photo.Photo()
        fo.category_id = c.id

        try:
            fo.save_user_image(self.session, pi, u.id, c.id)
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)
            assert(e.args[1] == "invalid user")

    def test_create_ballot_list_upload_category(self):
        # need to test when everything has been voted on max # of times
        # that we still get sent images
        self.setup()

        try:
            c = self.create_category()
            u = self.create_user()
            bm = voting.BallotManager()
            b = bm.create_ballot(self.session, u.id, c)
            assert(False)
        except Exception as e:
            assert(e.args[0] == errno.EINVAL and e.args[1] == 'category not in VOTING state')
            pass

    def test_voting_max(self):
        # need to test when everything has been voted on max # of times
        # that we still get sent images
        self.setup()
        tm = voting.TallyMan()

        # 1) create a category
        # 2) upload 4 images
        # 3) Vote on them multiple times

        c = self.create_category()

        # upload images
        u = self.create_user()
        # read our test file
        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        pi = photo.PhotoImage()
        pi._binary_image = ft.read()
        pi._extension = 'JPEG'

        _NUM_PHOTOS_UPLOADED = 40
        for i in range(0,_NUM_PHOTOS_UPLOADED):
            self.upload_image(pi, c, u)

        # switch category to voting state
        c.state = category.CategoryState.VOTING.value
        self.session.flush()

        # now create a new user
        nu = self.create_user()

        bm = voting.BallotManager()
        for i in range(0,_NUM_PHOTOS_UPLOADED+1): # need to ask for enough ballots to test all cases
            b = bm.create_ballot(self.session, nu.id, c)
            self.session.flush() # write ballot/ballotentries to DB
            j_votes = []
            idx = 1
            for be in b._ballotentries:
                j_votes.append({'bid': be.id, 'vote': idx})
                idx += 1

            bm.tabulate_votes(self.session, nu.id, j_votes)

        # okay, round #1 is over, let's initiate round #2
        self.session.execute('CALL sp_advance_category_round2()')

        # Now we are in round 2, get the category
        self.session.refresh(c)

        # for debugging, get the voting round
        q = self.session.query(voting.VotingRound).\
            join(photo.Photo, photo.Photo.id == voting.VotingRound.photo_id).\
            filter(photo.Photo.category_id == c.id).limit(1000)
        vr = q.all()

        # vote again!!
        for i in range(0,_NUM_PHOTOS_UPLOADED+1):
            b = bm.create_ballot(self.session, nu.id, c)
            self.session.flush() # write ballot/ballotentries to DB
            j_votes = []
            idx = 1
            for be in b._ballotentries:
                j_votes.append({'bid': be.id, 'vote': idx})
                idx += 1

            bm.tabulate_votes(self.session, nu.id, j_votes)

        # we need to clean up
        # clear out VotingRound table entries
        # clear out BallotEntry
        # clear out Ballot
        # clear out Photo
        # clear out Category & Resource

 #       self.teardown()

    def test_get_leaderboard_by_category_no_session(self):
        tm = voting.TallyMan()

        hndlr = dbg_handler.DebugHandler()
        logger.addHandler(hndlr)

        lb = tm.get_leaderboard_by_category(None, 1, True)
        assert(lb is None)
        log = hndlr._dbg_log
        assert(log is not None)
        assert(log['msg'] == "error getting leader board by category")

    def test_update_leaderboard_no_arguments(self):
        tm = voting.TallyMan()

        hndlr = dbg_handler.DebugHandler()
        logger.addHandler(hndlr)
        try:
            lb = tm.update_leaderboard(None, None, None, True)
            assert(False)
        except:
            log = hndlr._dbg_log
            assert(log is not None)
            assert(log['msg'] == "error updating the leaderboard")
