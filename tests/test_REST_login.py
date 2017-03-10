import os
import unittest
import uuid
import hashlib
import iiServer
import json
import base64
import datetime
from models import category, resources


class TestUser():
    _u = None   # username
    _p = None   # password
    _g = None   # guid
    _uid = None  # user_id
    _cid = None #category id

    def create_anon_user(self):
        self._u = str(uuid.uuid1())
        self._u = self._u.translate({ord(c): None for c in '-'})
        self._p = hashlib.sha224(self._u.encode('utf-8')).hexdigest()
        self_g = self._u
        return

    def create_user(self):
        self._p = 'pa55w0rd'
        self._g = str(uuid.uuid1())
        self._g = self._g.translate({ord(c): None for c in '-'})

        # real users have emails as their username
        self._u = self._g + '@gmail.com'
        return

    def get_username(self):
        return self._u
    def get_password(self):
        return self._p
    def set_password(self, p):
        self._p = p
        return
    def get_guid(self):
        return self._g
    def get_uid(self):
        return self._uid
    def set_uid(self, user_id):
        self._uid = user_id
        return
    def get_uid(self):
        return self._uid
    def set_cid(self, category_id):
        self._cid = category_id
    def get_cid(self):
        return self._cid

class TestLogin(unittest.TestCase):

    _test_users = []

    def setUp(self):
        self.app = iiServer.app.test_client()

    @staticmethod
    def is_guid(username, password):
        # okay we have a suspected guid/hash combination
        # let's figure out if this is a guid by checking the
        # hash
        hashed_username= hashlib.sha224(username.encode('utf-8')).hexdigest()
        if (hashed_username == password):
            return True

        return False

    def post_registration(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        g = tu.get_guid()
        rsp = self.app.post('/register', data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type':'application/json'})
        return rsp

    def post_auth(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        rsp = self.app.post('/auth', data=json.dumps(dict(username=u, password=p)),
                            headers={'content-type': 'application/json'})
        return rsp

    def post_login(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        rsp = self.app.post('/login', data=json.dumps(dict(username=u, password=p)),
                            headers={'content-type': 'application/json'})
        return rsp

    def test_user_registration(self):
        tu = TestUser()
        tu.create_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)
        return tu

    def test_anon_registration(self):
        tu = TestUser()
        tu.create_anon_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)
        return

    def test_double_anon_registration(self):
        tu = TestUser()
        tu.create_anon_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)

        # okay, try registering the same anonymous user again!
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 400)
        return

    def test_double_user_registration(self):
        tu = TestUser()
        tu.create_user()
        rsp = self.post_registration(tu)
        assert (rsp.status_code == 201)

        # okay, try registering the same anonymous user again!
        rsp = self.post_registration(tu)
        assert (rsp.status_code == 400)
        return

    def test_auth(self):
        # first register a user
        tu = TestUser()
        tu.create_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)

        # now login and get a token
        rsp = self.post_auth(tu)
        assert(rsp.status_code == 200)
        return

    def test_bad_password_auth(self):
        # first register a user
        tu = TestUser()
        tu.create_user()
        rsp = self.post_registration(tu)
        assert (rsp.status_code == 201)

        # now login and get a token
        tu.set_password('dummy password')
        rsp = self.post_auth(tu)
        assert (rsp.status_code == 401)
        return

    def test_login(self):
        # first create a user
        tu = TestUser()
        tu.create_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)

        # now login and get a token
        rsp = self.post_login(tu)
        assert(rsp.status_code == 200)
        assert(rsp.content_type == 'application/json')
        data = json.loads(rsp.data.decode("utf-8"))
        uid = data['user_id']
        cid = data['category_id']
        tu.set_uid(uid)
        tu.set_cid(cid)
        return tu


class TestPhotoUpload(unittest.TestCase):

    def setUp(self):
        self.app = iiServer.app.test_client()

    def test_photo_upload(self):

        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()

        tl = TestLogin()
        tl.setUp()
        tu = tl.test_login() # this will register (create) and login an user, returning the UID

        # we have our user, now we need a photo to upload
        ft = open('../photos/Suki.JPG', 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        # okay, we need to post this
        uid = tu.get_uid()
        cid = tu.get_cid()
        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        rsp = self.app.post('/photo', data=json.dumps(dict(user_id=uid, category_id=cid, extension=ext, image=b64img)),
                            headers={'content-type': 'application/json'})

        assert(rsp.status_code == 201)
        return
