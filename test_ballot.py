from unittest import TestCase
import voting
import resources
import category
import datetime
import usermgr
import initschema
import dbsetup

class TestBallot(TestCase):

    def test_write_ballot(self):

        session = dbsetup.Session()

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(session, r)

        # now create our category
        s_date = datetime.datetime.now()
        e_date =  s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date)
        category.Category.write_category(session, c)

        # create a user
        au = usermgr.AnonUser.create_anon_user(session, '99275132efe811e6bc6492361f002672')
        if au is not None:
            u = usermgr.User.create_user(session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        # let's created a ballot
        b = voting.Ballot(c.id, u.id)

        # we need to clean up
        session.delete(b)
        session.delete(u)
        session.delete(au)
        session.delete(c)
        session.delete(r)
