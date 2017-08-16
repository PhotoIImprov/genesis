
from unittest import TestCase
from models import admin
from models import usermgr
from tests import DatabaseTest
from datetime import datetime, timedelta
from sqlalchemy import func

class TestBaseURL(DatabaseTest):
    def test_default_url(self):
        self.setup()
        url = admin.BaseURL.default_url()
        assert(url == 'https://api.imageimprov.com/')

    def test_nomapping_url(self):
        self.setup()
        url = admin.BaseURL.get_url(self.session, 0)
        assert(url == 'https://api.imageimprov.com/')
        self.teardown()

    def test_mapped_url(self):
        self.setup()

        b = admin.BaseURL()
        b.url = 'https://www.imageimprov.com:8080/'
        self.session.add(b)
        self.session.commit()

        uids = self.session.query(func.max(usermgr.AnonUser.id)).first()
        uid = uids[0]

        au = self.session.query(usermgr.AnonUser).get(uid)
        assert(au is not None)
        au.base_id = b.id
        self.session.commit()

        url = admin.BaseURL.get_url(self.session, b.id)
        assert(url == b.url)
        self.teardown()

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

    def test_read_bad_template(self):

        try:
            bad_template = admin.read_template('foobar')
            assert(bad_template is not None)
        except Exception as e:
            pass

    def test_read_change_password_template(self):
        try:
            change_pwd_template = admin.read_template('/email/reset_password.html')
            assert(change_pwd_template is not None)
        except Exception as e:
            assert(False)

    def test_read_password_changed_template(self):
        try:
            template = admin.read_template('/email/password_changed.html')
            assert (template is not None)
        except Exception as e:
            assert (False)

    def test_csrfevent_been_used(self):
        ce = admin.CSRFevent(1, 24)
        assert(not ce.been_used)
        assert(ce.isvalid())

        ce.marked_used()
        assert(ce.been_used)
        assert(not ce.isvalid())

        ce.expiration_date = datetime.now() - timedelta(days=1)
        ce.been_used = False
        assert(not ce.isvalid())