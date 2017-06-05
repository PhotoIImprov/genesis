from unittest import TestCase
import initschema
import datetime
import os, errno
import uuid
from models import resources
from models import category, photo, usermgr, voting, sql_logging
from tests import DatabaseTest
import dbsetup
import logsetup
import logging
from sqlalchemy.sql import func

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

    def test_update_friendship_no_args(self):
        r = usermgr.FriendRequest.update_friendship(None, None, None, None)
        assert(r == None)

    def test_create_anon_user_no_args(self):
        success = usermgr.AnonUser.create_anon_user(None, None)
        assert(not success)

    def test_get_anon_user_by_id_no_args(self):
        au = usermgr.AnonUser.get_anon_user_by_id(None, None)
        assert(au is None)

    def test_find_anon_user_no_args(self):
        au = usermgr.AnonUser.find_anon_user(None, None)
        assert(au is None)

    def test_find_anon_user_not_exists(self):
        self.setup()
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.find_anon_user(self.session, guid)
        assert(au is None)
        self.teardown()

    def test_authenticate_not_exist_not_DEBUG(self):
        self.setup()
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        username = 'testuser@foo.us'
        password = guid + username
        dbsetup._DEBUG = False

        num_logs_before = self.session.query(sql_logging.Log).count()
        au = usermgr.authenticate(username, password)
        assert(au is None)
        num_logs_after = self.session.query(sql_logging.Log).count()
#        assert(num_logs_before == num_logs_after)
        self.teardown()

    def test_authenticate_not_exist_DEBUG(self):
#        self.setup()
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        username = 'testuser@foo.us'
        password = guid + username
        dbsetup._DEBUG = True
        logsetup.logger.setLevel(logging.DEBUG)
        logsetup.hndlr.setLevel(logging.DEBUG)
        self.session = dbsetup.Session()
        num_logs_before = self.session.query(func.count(sql_logging.Log.id)).one()
        au = usermgr.authenticate(username, password)
        assert (au is None)
        num_logs_after = self.session.query(func.count(sql_logging.Log.id)).one()
#        assert (num_logs_before < num_logs_after)
#        self.teardown()
