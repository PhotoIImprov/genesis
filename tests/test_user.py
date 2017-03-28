from unittest import TestCase
import initschema
import datetime
import os, errno
import uuid
from models import resources
from models import category, photo, usermgr, voting
from tests import DatabaseTest


class TestUserMgr(DatabaseTest):
    def test_change_password(self):
        self.setup()
        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        assert (au is not None)
        uname = 'harry.collins@gmail.com'
        u = usermgr.User.create_user(self.session, au.guid, uname, 'pa55w0rd')
        assert (u is not None)
        newpassword = "12345"
        u.change_password(self.session, newpassword)
        self.teardown()

    def test_create_user(self):
        self.setup()
        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        assert (au is not None)
        uname = 'harry.collins-gmail.com' # no @
        u = usermgr.User.create_user(self.session, au.guid, uname, 'pa55w0rd')
        assert (u is None)
        uname = 'harry.collins@gmail.com'
        u = usermgr.User.create_user(self.session, '99275132efe811e6bc6492361f002673', uname, 'pa55w0rd')
        assert (u is not None)

        self.teardown()

class TestFriend(DatabaseTest):

    def test_friend_request(self):
        self.setup()

        fr = usermgr.FriendRequest()

        self.teardown()

    def test_friend(self):
        self.setup()

        f = usermgr.Friend()

        self.teardown()

