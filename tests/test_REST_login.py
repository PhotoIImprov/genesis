import os
import unittest
import uuid
import hashlib
import iiServer
import json
import base64
import datetime
from models import category, resources
from collections import namedtuple
import requests

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

    def create_user_with_name(self, username):
        self.create_user()
        self.set_username(username)
        return

    def get_username(self):
        return self._u
    def set_username(self,username):
        self._u = username
        return
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
        rsp = self.app.post(path='/register', data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type':'application/json'})
        return rsp

    def post_auth(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        rsp = self.app.post(path='/auth', data=json.dumps(dict(username=u, password=p)),
                            headers={'content-type': 'application/json'})
        return rsp

    def post_login(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        rsp = self.app.post(path='/login', data=json.dumps(dict(username=u, password=p)),
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
        rsp = self.app.post(path='/photo', data=json.dumps(dict(user_id=uid, category_id=cid, extension=ext, image=b64img)),
                            headers={'content-type': 'application/json'})

        assert(rsp.status_code == 201)
        return

class TesttVoting(unittest.TestCase):

    def setUp(self):
        self.app = iiServer.app.test_client()

    def test_get_ballot(self):
        # let's retrieve a ballot we can vote on
        # we'll need to create some users, and then
        # upload some images

        return

    def test_ballot(self):
        # we need to post a set of ballots with votes
        tp = TestPhotoUpload()
        tp.setUp()
        for idx in range(10):
            tp.test_photo_upload() # create a user & upload a photo

        # let's create a user
        tl = TestLogin()
        tl.setUp()
        tu = tl.test_login() # this will register (create) and login an user, returning the UID
        uid = tu.get_uid()
        cid = tu.get_cid()
        rsp = self.app.get(path='/ballot', data=json.dumps(dict(user_id=uid, category_id=cid)),
                            headers={'content-type': 'application/json'})

        data = json.loads(rsp.data.decode("utf-8"))

        Ballot = namedtuple('ballot', 'bid, image')

        ballots = [Ballot(**k) for k in data["ballots"]]

        for be_dict in ballots:
            bid = be_dict.bid
            image = be_dict.image
            path = "/mnt/image_files/thumb{}.jpeg".format(bid)
            thumbnail = base64.b64decode(image)
            fp = open(path, "wb")
            fp.write(thumbnail)
            fp.close()

        return


# ************************************************************************
# ************************************************************************
# **                                                                    **
# ** INITIALIZE ENVIRONMENT                                             **
# **                                                                    **
# **                                                                    **
# **                                                                    **
# ************************************************************************
# ************************************************************************

class InitEnvironment(unittest.TestCase):

    _photos = {'Cute_Puppy.jpg',
              'Emma Passport.jpg',
              'Galaxy Edge 7 (full res)jpg.jpg',
              'Galaxy Edge 7 Cat (full res)jpg.jpg',
              'Galaxy Edge 7 Office Desk (full res, hdr).jpg',
              'Hawaii Palm Tree.JPG',
              'iPhone 6 Spider web (full res).JPG',
              'iPhone 7 statue and lake (full res).jpg',
              'iPhone 7 Yellow Rose (full res).jpg',
              'Netsoft USA Company Picture 1710.jpg',
              'PrimRib.JPG',
              'Suki.JPG',
              'Turtle.JPG'}

    _users = {'hcollins@gmail.com',
             'bp100a@hotmail.com',
             'dblankley@blankley.com',
             'regcollins@hotmail.com',
             'qaetre@hotmail.com',
             'hcollins@prizepoint.com',
             'hcollins@exit15w.com',
             'harry.collins@epam.com',
             'crazycow@netsoft-usa.com'}

    _base_url = None

    def test_photo_upload(self, tu, photo_name):

        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()

        # we have our user, now we need a photo to upload
        fn = '../photos/' + photo_name
        ft = open(fn, 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        # okay, we need to post this
        uid = tu.get_uid()
        cid = tu.get_cid()
        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        url = self._base_url + '/photo'
        rsp = requests.post(url, data=json.dumps(dict(user_id=uid, category_id=cid, extension=ext, image=b64img)), headers={'content-type':'application/json'})
#        assert(rsp.content_type == 'application/json')
        assert(rsp.status_code == 201)
        return

    def register_and_login(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        g = tu.get_guid()
        url = self._base_url + '/register'
        rsp = requests.post(url, data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type':'application/json'})
#        assert(rsp.content_type == 'application/json')
        assert(rsp.status_code == 400 or rsp.status_code == 201)

         # now let's login this user
        url = self._base_url + '/login'
        rsp = requests.post(url, data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type':'application/json'})
        assert(rsp.status_code == 200)

        if rsp.status_code == 200:
            data = json.loads(rsp.content.decode("utf-8"))
            uid = data['user_id']
            cid = data['category_id']
            tu.set_uid(uid)
            tu.set_cid(cid)

        return rsp

    def test_initialize_server(self):

        # okay, we're going to create users & upload photos
        self._base_url = 'http://104.198.176.198:8080'
        user_list = []
        for uname in self._users:
            tu = TestUser()
            tu.create_user_with_name(uname)
            rsp = self.register_and_login(tu)
            user_list.append(tu)

        # okay, we've registered & logged in our users
        # Now let's upload some images
        for tu in user_list:
            for pn in self._photos:
                self.test_photo_upload(tu, pn)


        return