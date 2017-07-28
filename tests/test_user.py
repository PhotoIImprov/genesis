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
from handlers import dbg_handler
from logsetup import logger

class TestUserMgr(DatabaseTest):

    def test_change_password(self):
        self.setup()
        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        assert (au is not None)
        uname = 'harry.collins@gmail.com'
        u = usermgr.User.create_user(self.session, au.guid, uname, 'pa55w0rd')
        assert(u is not None)
        self.session.commit()

        first_hashedPWD = u.hashedPWD

        # read this password, it'll be hashed
        u_pwd = self.session.query(usermgr.User).get(u.id)
        assert(u_pwd is not None)

        newpassword = "12345"
        u.change_password(self.session, newpassword)
        self.session.commit()
        u2_pwd = self.session.query(usermgr.User).get(u.id)

        assert(first_hashedPWD != u2_pwd.hashedPWD)

        self.teardown()

    def test_random_password(self):
        self.setup()
        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        assert (au is not None)
        uname = 'harry.collins@gmail.com'
        u = usermgr.User.create_user(self.session, au.guid, uname, 'pa55w0rd')
        assert (u is not None)
        newpassword = "12345"
        u.change_password(self.session, newpassword)

        pwd = u.random_password(6)
        assert(len(pwd) == 6)

        pwd = u.random_password(10)
        assert(len(pwd) == 10)

        self.teardown()

    def test_forgot_password(self):
        self.setup()
        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        assert (au is not None)
        uname = 'bp100a@gmail.com'
        u = usermgr.User.create_user(self.session, au.guid, uname, 'pa55w0rd')
        assert (u is not None)
        http_status = u.forgot_password(self.session)
        assert(http_status == 200)

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

        hndlr = dbg_handler.DebugHandler()
        logger.addHandler(hndlr)
        hndlr._dbg_log = None
        logsetup.logger.setLevel(logging.INFO)
        logsetup.hndlr.setLevel(logging.INFO)

        au = usermgr.authenticate(username, password)
        assert(au is None)
        log = hndlr._dbg_log
        assert(log is None)
        self.teardown()

    def test_authenticate_not_exist_DEBUG(self):
        self.setup()
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        username = 'testuser@foo.us'
        password = guid + username
        dbsetup._DEBUG = True

        hndlr = dbg_handler.DebugHandler()
        logger.addHandler(hndlr)
        logsetup.logger.setLevel(logging.DEBUG)
        logsetup.hndlr.setLevel(logging.DEBUG)

        au = usermgr.authenticate(username, password)
        assert (au is None)
        log = hndlr._dbg_log
        assert(log is not None)
        self.teardown()