from unittest import TestCase
from models import admin
from models import usermgr
from tests import DatabaseTest
from datetime import datetime, timedelta

class TestCSRFevent(DatabaseTest):

    def test_generate_csrf_token(self):
        a = admin.CSRFevent(1, 24)
        assert(len(a.csrf) == 32)

    def test_csrfevent_expiration(self):
        self.setup()

        u = usermgr.User.find_user_by_id(self.session, 1)
        a = admin.CSRFevent(u.id, 1)
        assert(a.expiration_date > datetime.now())
        self.teardown()

    def test_read_csrfevent(self):
        self.setup()

        u = usermgr.User.find_user_by_id(self.session, 1)
        a = admin.CSRFevent(u.id, 1)
        self.session.add(a)
        self.session.commit()

        csrfevent = admin.CSRFevent.get_csrfevent(self.session, a.csrf)
        assert(csrfevent is not None)
        assert(csrfevent.user_id == a.user_id)
        assert(csrfevent.expiration_date == a.expiration_date)
        self.teardown()