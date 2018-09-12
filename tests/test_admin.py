from unittest import TestCase
from models import admin
from models import usermgr, category, photo
from tests import DatabaseTest
from datetime import datetime, timedelta
from sqlalchemy import func
from controllers import categorymgr
import uuid
import errno

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

        guid = str(uuid.uuid1())
        guid = guid.translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(self.session, guid)
        self.session.add(au)
        self.session.commit()

        a = admin.CSRFevent(au.id, expiration_hours=1)
        assert(a.expiration_date > datetime.now())
        self.teardown()

    def test_read_csrfevent(self):
        self.setup()

        guid = str(uuid.uuid1())
        guid = guid.translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(self.session, guid)
        self.session.add(au)
        self.session.commit()

        a = admin.CSRFevent(au.id, expiration_hours=1)
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
            change_pwd_template = admin.Emailer().read_template('/email/reset_password.html')
            assert(change_pwd_template is not None)
        except Exception as e:
            assert(False)

    def test_read_password_changed_template(self):
        try:
            template = admin.Emailer().read_template('/email/password_changed.html')
            assert (template is not None)
        except Exception as e:
            assert (False)

    def test_csrfevent_been_used(self):
        self.setup()
        ce = admin.CSRFevent(1, 24)
        assert(not ce.been_used)
        assert(ce.isvalid())

        ce.mark_used()
        assert(ce.been_used)
        assert(not ce.isvalid())

        ce.expiration_date = datetime.now() - timedelta(days=1)
        ce.been_used = False
        assert(not ce.isvalid())
        self.teardown()

    def test_category_photo_list(self):
        self.setup()

        guid = str(uuid.uuid1())
        guid = guid.translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(self.session, guid)
        self.session.add(au)

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})
        start_date = datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(self.session, category.CategoryType.OPEN.value)
        self.session.commit()

        num_photos = 5
        for i in range (1,num_photos+1):
            p = photo.Photo()
            p.category_id = c.id
            p.filepath = 'boguspath'
            p.filename = str(uuid.uuid1()).translate({ord(c): None for c in '-'})
            p.user_id = au.id
            p.times_voted = 0
            p.score = i*4
            p.likes = 0
            p.active = 1
            self.session.add(p)

        self.session.commit()

        # okay we have a new user, a new category, and the category has 5 photos

        pl = cm.category_photo_list(self.session, 'next', 0, c.id)
        assert(pl is not None)
        assert(len(pl) == num_photos)

        pl = cm.category_photo_list(self.session, 'prev', pl[num_photos-1].id, c.id)
        assert(pl is not None)
        assert(len(pl) == num_photos-1)

        c.state = category.CategoryState.CLOSED.value;
        self.session.commit()

        pl = cm.category_photo_list(self.session, 'next', 0, c.id)
        for p in pl:
            p.active = 0
            self.session.add(p)
        self.session.commit()
        self.teardown()

    @staticmethod
    def f_tst_send_forgot_password_send_email(to_email:str, from_email: str, subject_email: str, body_email:str) -> int:

        assert to_email == 'bp100a@hotmail.com'
        assert from_email == 'Forgot Password <noreply@imageimprov.com>'
        assert subject_email == 'Password reset'
        return 200

    def test_send_forgot_password_email(self):

        emailaddress = 'bp100a@hotmail.com'
        status = admin.Emailer(f_sendemail=TestCSRFevent.f_tst_send_forgot_password_send_email).send_forgot_password_email(emailaddress, 'fake_csrftoken')
        assert(status == 200)

    @staticmethod
    def f_tst_send_password_changed_send_email(to_email: str, from_email: str, subject_email: str,
                                               body_email: str) -> int:

        assert to_email == 'bp100a@hotmail.com'
        assert from_email == 'Password Change <noreply@imageimprov.com>'
        assert subject_email == 'Password Change notification'
        return 200

    def test_send_password_changed_email(self):

        emailaddress = 'bp100a@hotmail.com'
        status = admin.Emailer(f_sendemail=TestCSRFevent.f_tst_send_password_changed_send_email).send_reset_password_notification_email(emailaddress)
        assert (status == 200)

    def test_bad_template_name(self):
        try:
            admin.Emailer().read_template('bogustemplatename')
            assert(False)
        except Exception as e:
            assert(e.args[0] == errno.ENOENT and e.args[1] == 'No such file or directory')
