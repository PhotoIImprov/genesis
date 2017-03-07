from unittest import TestCase
import initschema
import datetime
import os, errno
import uuid
from models import resources
from models import voting, category, usermgr
from . import DatabaseTest

class TestLeaderBoard(DatabaseTest):

    def test_new_leader(self):
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
        for idx in range(10):
            guid = 'AFA3540CCDD24B8686E3DDD75D84EF' + '{0:02d}'.format(idx)
            au = usermgr.AnonUser.create_anon_user(self.session, guid)
            if au is not None:
                email = 'testlb_{}@gmail.com'.format(idx)
                u = usermgr.User.create_user(self.session, au.guid, email, 'pa55w0rd')
            # now add each user to the leader board
            voting.LeaderBoard.update_leaderboard(self.session, u.id, c.id, 1, 2, idx)

        leaders = voting.LeaderBoard.leaderboard_list(self.session, c.id)
        assert(leaders is not None)
        assert(len(leaders) > 0)

        return
