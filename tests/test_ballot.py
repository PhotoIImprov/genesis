from . import DatabaseTest
import voting
import resources
import category
import datetime
import usermgr

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
        category.PhotoIndex.create_index(self.session, c.id)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        # let's created a ballot
        b = voting.Ballot(c.id, u.id)

        # we need to clean up
        self.teardown()
