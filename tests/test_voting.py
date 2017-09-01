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
from flask import Flask, jsonify
import json
import dbsetup
from controllers import categorymgr

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

        th, p = tm.read_thumbnail(self.session, 0)
        assert(th == None and p == None)

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

        if tm.leaderboard_exists(self.session, c):
            lb = tm.get_leaderboard_by_category(self.session, c, check_exist=True)
            lb.delete_leaderboard()

        lb = tm.get_leaderboard_by_category(self.session, c, check_exist=False)
        assert(lb is not None)

        # we have a leaderboard for this category, create an empty key
        lb.rank_member('0', 0, '0') # member, score, member_data
        try:
            d = tm.fetch_leaderboard(self.session, 1, c)
            assert(d is not None)
            assert(len(d) == 0)
        except Exception as e:
            assert(False)
        self.teardown()

    def test_leaderboard_invalid_category(self):
        self.setup()
        tm = voting.TallyMan()
        c = category.Category()
        c.id = 0

        dl = tm.fetch_leaderboard(self.session, 0, c)
        assert(dl is not None)
        assert(len(dl) == 0)

        self.teardown()

    def test_leaderboard_invalid_category_nocheck(self):
        self.setup()
        tm = voting.TallyMan()
        lb = tm.get_leaderboard_by_category(self.session, None, check_exist=False)
        assert(lb is None)
        self.teardown()

    def test_create_displayname_anonymous(self):
        self.setup()
        tm = voting.TallyMan()

        # create a user
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})

        au = usermgr.AnonUser.create_anon_user(self.session, guid)
        self.session.flush()
        name = tm.create_displayname(self.session, au.id)

        assert(name == 'anonymous{}'.format(au.id))
        self.teardown()

    def create_category(self, category_name):
        # first we need a resource
        max_resource_id = self.session.query(func.max(resources.Resource.resource_id)).one()
        rid = max_resource_id[0] + 1
        r = resources.Resource.create_resource(rid, 'EN', category_name)
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
            c = self.create_category('round 2 testing')
            u = self.create_user()
            bm = voting.BallotManager()
            b = bm.create_ballot(self.session, u.id, c, allow_upload=False)
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

        c = self.create_category('test_voting_max')

        # upload images
        u = self.create_user()
        # read our test file
        ft = open('../photos/TEST4.JPG', 'rb')
        pi = photo.PhotoImage()
        pi._binary_image = ft.read()
        ft.close()
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

        self.teardown()

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

    def get_active_user(self):
        max_uid = self.session.query(func.max(usermgr.AnonUser.id)).one()
        au = self.session.query(usermgr.AnonUser).get(max_uid[0])
        return au

    def get_active_photo(self):
        max_pid = self.session.query(func.max(photo.Photo.id)).one()
        return max_pid[0]

    def test_ballotentry_with_tags(self):
        self.setup()

        # create a new category so we can add tags to it!
        au = self.get_active_user()
        category_description = 'test_ballot_entry_with_tags()'
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(self.session, category.CategoryType.OPEN.value)

        tag_list = category.CategoryTagList()
        for i in range(1,5):
            r = cm.create_resource(self.session,'tag{0}'.format(i))
            ctag = category.CategoryTag(category_id=c.id, resource_id = r.resource_id)
            self.session.add(ctag)

        self.session.commit()

        tag_list.read_category_tags(c.id, self.session)

        # Now create a ballot entry for this category
        pid = self.get_active_photo()
        be = voting.BallotEntry(user_id=au.id, category_id=c.id, photo_id=pid)
        be.bid = 1
        be.orientation = 6
        be.image = b'\x00\x00\0x1'
        be._tags = tag_list
        be._photo = self.session.query(photo.Photo).get(be.photo_id)

        d = be.to_json()
        assert (d is not None)

        j = json.dumps(d)
        assert(j is not None)
        self.teardown()


    def test_voting_with_tags(self):
        # need to test we can submit a ballotentry (vote) with tags
        self.setup()
        tm = voting.TallyMan()

        # 1) create a category
        # 2) upload 4 images
        # 3) Vote on them with 'tags' specified

        c = self.create_category('test_voting_with_tags')

        # upload images
        u = self.create_user()
        # read our test file
        ft = open('../photos/TEST3.JPG', 'rb')
        pi = photo.PhotoImage()
        pi._binary_image = ft.read()
        ft.close()
        pi._extension = 'JPEG'

        _NUM_PHOTOS_UPLOADED = 4
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
                j_votes.append({'bid': be.id, 'vote': idx, 'tags':['tag1', 'tag2', 'tag3']})
                idx += 1

            bel = bm.tabulate_votes(self.session, nu.id, j_votes)

            assert(bel is not None)

        self.teardown()

    def test_voting_offensive(self):
        # need to test we can submit a ballotentry (vote) with offensive flag
        self.setup()
        tm = voting.TallyMan()

        # 1) create a category
        # 2) upload 4 images
        # 3) Vote on them with 'tags' specified

        c = self.create_category('test_voting_offensive')

        # upload images
        u = self.create_user()
        # read our test file
        ft = open('../photos/TEST6.JPG', 'rb')
        pi = photo.PhotoImage()
        pi._binary_image = ft.read()
        pi._extension = 'JPEG'
        ft.close()

        _NUM_PHOTOS_UPLOADED = 4
        for i in range(0, _NUM_PHOTOS_UPLOADED):
            self.upload_image(pi, c, u)

        # switch category to voting state
        c.state = category.CategoryState.VOTING.value
        self.session.flush()

        # now create a new user
        nu = self.create_user()

        bm = voting.BallotManager()
        for i in range(0, _NUM_PHOTOS_UPLOADED + 1):  # need to ask for enough ballots to test all cases
            b = bm.create_ballot(self.session, nu.id, c)
            self.session.flush()  # write ballot/ballotentries to DB
            j_votes = []
            idx = 1
            for be in b._ballotentries:
                if idx == 2:
                    j_votes.append({'bid': be.id, 'vote': idx}) # same as 0
                else:
                    j_votes.append({'bid': be.id, 'vote': idx, 'offensive': str(idx%2), 'like': str(idx%2)})
                idx += 1

            bel = bm.tabulate_votes(self.session, nu.id, j_votes)
            assert(bel is not None)
            assert(len(bel) == 4)

            #make sure offensive/like flags were parsed properly
            idx = 1
            for be in bel:
                offensive = be.offensive
                like = be.like
                assert(offensive == idx%2 and like == idx%2)
                idx += 1

        self.teardown()

    # NOTE: Hashing test for duplicates eliminated
    # def test_cleanup_list_noduplicates(self):
    #     bm = voting.BallotManager()
    #
    #     # create our synthetic list of photos
    #     photo_list = []
    #     for i in range(0,20):
    #         thumb_hash = i & 0x3 # only 4 hashes
    #         p = photo.Photo()
    #         photo_list.append(p)
    #         pm = photo.PhotoMeta(720, 720, thumb_hash)
    #         p.id = i
    #         pm.id = i
    #         p._photometa = pm
    #
    #     clean_list = bm.cleanup_list(photo_list, 4)
    #     assert(len(clean_list) == 4)
    #
    #     #scour the list for duplicates
    #     duplicate = False
    #     for p in clean_list:
    #         hash = p._photometa.thumb_hash
    #         for q in clean_list:
    #             if p != q and hash != 0 and hash == q._photometa.thumb_hash:
    #                 assert(False) # duplicate found!
    #
    #
    # def test_cleanup_list_allduplicates(self):
    #     bm = voting.BallotManager()
    #
    #     # create our synthetic list of photos
    #     photo_list = []
    #     for i in range(0,20):
    #         thumb_hash = 0x5555 # all hashes the same
    #         p = photo.Photo()
    #         photo_list.append(p)
    #         pm = photo.PhotoMeta(720, 720, thumb_hash)
    #         p.id = i
    #         pm.id = i
    #         p._photometa = pm
    #
    #     clean_list = bm.cleanup_list(photo_list[:], 4)
    #     assert(len(clean_list) == 4)
    #
    #     assert(clean_list[0]._photometa.thumb_hash == clean_list[1]._photometa.thumb_hash)
    #
    #     is_shuffled = False
    #     for i in range(0,4):
    #         if clean_list[i] != photo_list[i]:
    #             is_shuffled = True
    #     assert(is_shuffled)

    def upload_images(self, num_images, u, c):
        ft = open('../photos/TEST1.JPG', 'rb')
        pi = photo.PhotoImage()
        pi._binary_image = ft.read()
        ft.close()
        pi._extension = 'JPEG'

        for i in range(0, num_images):
            self.upload_image(pi, c, u)

    def test_upload_ballot_return(self):
        '''
        Test that a ballot is return from an Upload category
        :return:
        '''

        # First, create UPLOAD category
        # Have user 'a' upload 40 images
        # Have user 'b' upload an image
        #     -> no ballot returned
        # have user 'a' upload 10 more images
        # have user 'c' request category list
        #     -> upload category NOT in list
        # have user 'c' upload 1 image
        #    -> ballot for upload category returned
        # have user 'c' request active category list
        #    -> upload category in ballot list
        #

        self.setup()

        bm = voting.BallotManager()

        c = self.create_category('upload ballot test')
        assert(c is not None)

        user_a = self.create_user()
        assert(user_a is not None)
        user_b = self.create_user()
        assert(user_b is not None)
        user_c = self.create_user()
        assert(user_b is not None)

        # upload 40 images for user a
        self.upload_images(dbsetup.Configuration.UPLOAD_CATEGORY_PICS - 5, user_a, c)

        self.upload_images(1, user_b, c)
        cl = bm.active_voting_categories(self.session, user_b.id)
        assert(cl is not None)
        for cat in cl:
            assert(cat.id != c.id)

        # okay, good, the Upload category isn't in the list. Now upload 10 more items for user 'A'

        self.upload_images(6, user_a, c)
        cl = bm.active_voting_categories(self.session, user_b.id)
        assert(cl is not None)
        found = False
        for cat in cl:
            if cat.id == c.id:
                found = True
                break
        assert(found) # we should find something

        self.teardown()
