from unittest import TestCase
from models import admin
from models import usermgr
from tests import DatabaseTest

class TestCSRFevent(DatabaseTest):

    def test_generate_csrf_token(self):
        a = admin.CSRFevent(1, 24)
        assert(len(a.csrf) == 32)

    def test_forgot_password(self):
        self.setup()

        u = usermgr.User.find_user_by_email(self.session, 'bp100a@hotmail.com')
        assert(u is not None)

        fpwd = admin.ForgotPassword()
        http_status = fpwd.forgot_password(self.session, u)
        assert(http_status == 200)

        self.teardown()
