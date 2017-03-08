import initschema
import datetime

from models import resources
from models import usermgr

from models import category, voting, photo
from . import DatabaseTest
import os

class TestBallot(DatabaseTest):

    def test_write_ballot(self):

        self.setup()
        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category & the image indexer
        s_date = datetime.datetime.now()
        e_date =  s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date)
        category.Category.write_category(self.session, c)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        # let's created a ballot
        b = voting.Ballot(c.id, u.id)

        # we need to clean up
        self.teardown()

    def test_create_ballot(self):
        self.setup()

        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()
        ft = open('photos/Cute_Puppy.jpg', 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category & the image indexer
        s_date = datetime.datetime.now()
        e_date = s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date)
        category.Category.write_category(self.session, c)

        # create a user
        for idx in range(10):
            guid = 'AFA3540CCDD24B8686E3DDD75D84EF' + '{0:02d}'.format(idx)
            au = usermgr.AnonUser.create_anon_user(self.session, guid)
            if au is not None:
                email = 'testlb_{}@gmail.com'.format(idx)
                u = usermgr.User.create_user(self.session, au.guid, email, 'pa55w0rd')
                # Now add a photo for this user
                # read our test file
                fo = photo.Photo()
                assert (fo is not None)
                fo.category_id = c.id
                fo.save_user_image(self.session, ph, "JPEG", au.id, c.id)

        # Now let's created a ballot
        b = voting.Ballot.create_ballot(self.session, u.id, c.id)

        self.teardown()
        return
