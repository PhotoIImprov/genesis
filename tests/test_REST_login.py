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

class TestUser:
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
        if hashed_username == password:
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

    def test_anon_authentication(self):
        tu = TestUser()
        tu.create_anon_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)
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

    def test_leaderboard_not_json(self):
        rsp = self.app.get(path='/leaderboard', headers={'content-type': 'text/html'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_ballot_not_json(self):
        rsp = self.app.get(path='/ballot', headers={'content-type': 'text/html'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_vote_not_json(self):
        rsp = self.app.post(path='/vote', headers={'content-type': 'text/html'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_photo_not_json(self):
        rsp = self.app.post(path='/photo', headers={'content-type': 'text/html'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_login_not_json(self):
        rsp = self.app.post(path='/login', headers={'content-type': 'text/html'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_register_not_json(self):
        rsp = self.app.post(path='/register', headers={'content-type': 'text/html'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_category_not_json(self):
        rsp = self.app.get(path='/category', headers={'content-type': 'text/html'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_category_no_userid(self):
        rsp = self.app.get(path='/category', data=json.dumps(dict(user_id=None, password='pa55w0rd') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'missing user id' and rsp.status_code == 400)

        rsp = self.app.get(path='/category', data=json.dumps(dict(password='pa55w0rd') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'missing user id' and rsp.status_code == 400)

        return rsp

    def test_login_missing_args(self):
        rsp = self.app.post(path='/login', data=json.dumps(dict(username=None, password='pa55w0rd') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        rsp = self.app.post(path='/login', data=json.dumps(dict(username='bp100a') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_photo_missing_args(self):
        rsp = self.app.post(path='/photo', data=json.dumps(dict(image=None, extension=None, category_id=None, user_id=None) ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'missing arguments' and rsp.status_code == 400)

        rsp = self.app.post(path='/photo', data=json.dumps(dict(username='bp100a') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'missing arguments' and rsp.status_code == 400)

        return rsp

    def test_register_missing_args(self):
        rsp = self.app.post(path='/register', data=json.dumps(dict(username=None, password='pa55w0rd') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        rsp = self.app.post(path='/register', data=json.dumps(dict(username='bp100a') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient arguments' and rsp.status_code == 400)

        return rsp

    def test_ballot_missing_args(self):
        rsp = self.app.get(path='/ballot', data=json.dumps(dict(user_id=None, category_id=1) ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'invalid arguments' and rsp.status_code == 400)

        rsp = self.app.get(path='/ballot', data=json.dumps(dict(username='bp100a') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'invalid arguments' and rsp.status_code == 400)

        return rsp

    def test_vote_missing_args(self):
        rsp = self.app.post(path='/vote', data=json.dumps(dict(user_id=None, votes=None) ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient JSON arguments' and rsp.status_code == 400)

        rsp = self.app.post(path='/vote', data=json.dumps(dict(username='bp100a') ), headers={'content-type': 'application/json'})
        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(error == 'insufficient JSON arguments' and rsp.status_code == 400)

        return rsp





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

    _uid = None
    def setUp(self):
        self.app = iiServer.app.test_client()

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
        self._uid = tu.get_uid()
        cid = tu.get_cid()
        rsp = self.app.get(path='/ballot', data=json.dumps(dict(user_id=self._uid, category_id=cid)),
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

        return ballots

    def test_ballot_invalid_user_id(self):
        rsp = self.app.get(path='/ballot', data=json.dumps(dict(user_id=0, category_id=0)),
                           headers={'content-type': 'application/json'})

        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(rsp.status_code == 500 and error == "no ballot created!")
        return

    def test_ballot_invalid_category_id(self):
        # let's create a user
        tl = TestLogin()
        tl.setUp()
        tu = tl.test_login() # this will register (create) and login an user, returning the UID
        self._uid = tu.get_uid()

        rsp = self.app.get(path='/ballot', data=json.dumps(dict(user_id=self._uid, category_id=0)),
                           headers={'content-type': 'application/json'})

        data = json.loads(rsp.data.decode("utf-8"))
        error = data['error']
        assert(rsp.status_code == 500 and error == "no ballot created!")
        return

    def test_voting(self):

        ballots = self.test_ballot() # read a ballot
        assert(ballots is not None)
        assert(self._uid is not None)

        votes = []
        idx = 1
        for be_dict in ballots:
            bid = be_dict.bid
            if (idx % 2) == 0:
                votes.append(dict({'bid':bid, 'vote':idx, 'like':"true"}))
            else:
                votes.append(dict({'bid': bid, 'vote': idx}))
            idx += 1

        jvotes = json.dumps(dict({'user_id': self._uid, 'votes':votes}))
        rsp = self.app.post(path='/vote', data=jvotes, headers={'content-type': 'application/json'})
        assert(rsp.status_code == 200)
        return rsp

    def test_voting_too_many(self):

        ballots = self.test_ballot() # read a ballot
        assert(ballots is not None)
        assert(self._uid is not None)

        votes = []
        idx = 1
        for be_dict in ballots:
            bid = be_dict.bid
            if (idx % 2) == 0:
                votes.append(dict({'bid':bid, 'vote':idx, 'like':"true"}))
            else:
                votes.append(dict({'bid': bid, 'vote': idx}))
        idx += 1

        votes.append(dict({'bid':0, 'vote':1, 'like':"true"})) # add extra so we fail!

        jvotes = json.dumps(dict({'user_id': self._uid, 'votes':votes}))
        rsp = self.app.post(path='/vote', data=jvotes, headers={'content-type': 'application/json'})
        assert(rsp.status_code == 413)
        return rsp

class TestCategory(unittest.TestCase):

    _uid = None
    def setUp(self):
        self.app = iiServer.app.test_client()


    def test_category(self):
        # let's create a user
        tl = TestLogin()
        tl.setUp()
        tu = tl.test_login()  # this will register (create) and login an user, returning the UID
        self._uid = tu.get_uid()

        rsp = self.app.get(path='/category', data=json.dumps(dict(user_id=self._uid)),
                            headers={'content-type': 'application/json'})

        assert(rsp.status_code == 200)

    def test_category_bogus_uid(self):
       # 0 is not a valid user id, so this should fail
        rsp = self.app.get(path='/category', data=json.dumps(dict(user_id=0)),
                            headers={'content-type': 'application/json'})

        assert(rsp.status_code == 500)
