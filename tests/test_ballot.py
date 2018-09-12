import initschema
import datetime

from models import resources
from models import usermgr
from models import category, voting, photo
from tests import DatabaseTest
import os
import json
from leaderboard.leaderboard import Leaderboard
from controllers import categorymgr

class TestBallot(DatabaseTest):

    def test_write_ballot(self):

        self.setup()
        # first we need a resource
        r = resources.Resource.load_resource_by_id(self.session, rid=5555, lang='EN')
        if r is None:
            try:
                r = resources.Resource.create_resource(rid=5555, language='EN', resource_str='Kittens')
                resources.Resource.write_resource(self.session, r)
            except Exception as e:
                assert(False)
        # now create our category & the image indexer
        s_date = datetime.datetime.now()
        e_date =  s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date, category.CategoryState.UPLOAD)
        category.Category.write_category(self.session, c)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        # let's created a ballot
        b = voting.Ballot(c.id, u.id)

        # we need to clean up
        self.teardown()

    @staticmethod
    def create_photo_fullpath(photo_name : str) -> str:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()
        if 'tests' in dir_path:
            photo_fullpath = dir_path.replace('tests', 'photos') + '/' + photo_name
        else:
            photo_fullpath = dir_path + '/' + photo_name
            
        return photo_fullpath
    
    def test_create_ballot(self):
        self.setup()

        file_pointer = open(self.create_photo_fullpath('TEST7.JPG'), 'rb')
        photo_image = photo.PhotoImage()
        photo_image._binary_image = file_pointer.read()
        photo_image._extension = 'JPEG'
        file_pointer.close()

        # first we need a resource
        # first we need a resource
        r = resources.Resource.load_resource_by_id(self.session, rid=5555, lang='EN')
        if r is None:
            r = resources.Resource.create_resource(rid=5555, language='EN', resource_str='Kittens')
            resources.Resource.write_resource(self.session, r)

        # now create our category & the image indexer
        s_date = datetime.datetime.now()
        e_date = s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date, category.CategoryState.UPLOAD)
        category.Category.write_category(self.session, c)

        # create a user
        for idx in range(10):
            guid = 'AFA3540CCDD24B8686E3DDD75D84EF' + '{0:02d}'.format(idx)
            anonymous_user = usermgr.AnonUser.create_anon_user(self.session, guid)
            if anonymous_user is not None:
                email = 'testlb_{}@gmail.com'.format(idx)
                known_user = usermgr.User.create_user(self.session, anonymous_user.guid, email, 'pa55w0rd')
                # Now add a photo for this user
                # read our test file
                fo = photo.Photo()
                fo.category_id = c.id
                fo.save_user_image(self.session, photo_image, anonymous_user.id, c.id)

        # now set this category to voting
        c.state = category.CategoryState.VOTING.value
        self.session.flush()

        # Now let's created a ballot
        b = categorymgr.BallotManager().create_ballot(self.session, known_user.id, c)
        assert(b is not None)
        json_string = b.to_json()
        json_size = len(json_string)
        self.teardown()
        return

    def test_leaderboard(self):

        # create new leaderboard
        test_lb = Leaderboard('test_leaderboard')
#        return

        test_lb.rank_member('TEST1', 1)
        test_lb.rank_member('TEST2', 2)
        test_lb.rank_member('TEST3', 3)
        test_lb.rank_member('TEST4', 4)
        test_lb.rank_member('TEST5', 5)
        test_lb.rank_member('TEST6', 6)

        # get leaderboard

        leaders = test_lb.leaders(1)
        total_members = test_lb.total_members()
        total_pages = test_lb.total_pages()
        score_1 = test_lb.rank_for('TEST1')
        score_2 = test_lb.rank_for('TEST2')

    def test_get_redis_server(self):
        self.setup()
        d = voting.ServerList().get_redis_server(self.session)
        port = d['port']
        ipaddress = d['ip']
        assert(port == 6379)

        self.teardown()
