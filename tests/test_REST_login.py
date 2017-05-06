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
from models import error
from urllib.parse import urlencode
from werkzeug.datastructures import Headers


class TestUser:
    _u = None   # username
    _p = None   # password
    _g = None   # guid
    _uid = None  # user_id
    _cid = None #category id
    _token = None # JWT token
    _ia = None # issued at

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
    def set_token(self, tk):
        self._token = tk
    def get_token(self):
        return self._token

class iiBaseUnitTest(unittest.TestCase):
    def setUp(self):
        self.app = iiServer.app.test_client()

    def get_header_json(self):
        assert(self.get_token() is not None)
        headers = Headers()
        headers.add('content-type', 'application/json')
        headers.add('Authorization', 'JWT ' + self.get_token())

        return headers

    def get_header_html(self):
        assert(self.get_token() is not None)
        headers = Headers()
        headers.add('content-type', 'text/html')
        headers.add('Authorization', 'JWT ' + self.get_token())
        return headers

    _token = None

    def set_token(self, tk):
        self._token = tk

    def get_token(self):
        return self._token

    def invalidate_token(self):
        self.set_token(None)

    def post_auth(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        rsp = self.app.post(path='/auth', data=json.dumps(dict(username=u, password=p)),
                            headers={'content-type': 'application/json'})
        return rsp

#    def post_login(self, tu):
#        u = tu.get_username()
#        p = tu.get_password()

        # don't call login if we are using JSON Web Tokens (JWT)
#        return self.post_auth(tu)


    def post_registration(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        g = tu.get_guid()
        rsp = self.app.post(path='/register', data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type': 'application/json'})
        return rsp

    def create_testuser_get_token(self):
        # first create a user
        tu = TestUser()
        tu.create_user()
        self.setUp()
        rsp = self.post_registration(tu)
        assert (rsp.status_code == 201)

        # now login and get a token
        rsp = self.post_auth(tu)
        assert (rsp.status_code == 200)
        assert (rsp.content_type == 'application/json')
        data = json.loads(rsp.data.decode("utf-8"))
        token = data['access_token']
        tu.set_token(token)
        self.set_token(token)

        return tu

    def create_anon_testuser_get_token(self):
        # first create a user
        tu = TestUser()
        tu.create_anon_user()
        self.setUp()
        rsp = self.post_registration(tu)
        assert (rsp.status_code == 201)

        # now login and get a token
        rsp = self.post_auth(tu)
        assert (rsp.status_code == 200)
        assert (rsp.content_type == 'application/json')
        data = json.loads(rsp.data.decode("utf-8"))
        token = data['access_token']
        tu.set_token(token)
        self.set_token(token)

        return tu


class TestLogin(iiBaseUnitTest):

    _test_users = []

    @staticmethod
    def is_guid(username, password):
        # okay we have a suspected guid/hash combination
        # let's figure out if this is a guid by checking the
        # hash
        hashed_username= hashlib.sha224(username.encode('utf-8')).hexdigest()
        if hashed_username == password:
            return True

        return False

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
        data = json.loads(rsp.data.decode("utf-8"))
        token = data['access_token']
        assert(rsp.status_code == 200 and token is not None)
        tu.set_token(token)
        tu._ia = datetime.datetime.now()
        return

    def test_anon_authentication(self):
        tu = TestUser()
        tu.create_anon_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)
        rsp = self.post_auth(tu)
        data = json.loads(rsp.data.decode("utf-8"))
        token = data['access_token']
        assert(rsp.status_code == 200 and token is not None)
        self.set_token(token)

        # see if token works
        rsp = self.app.get(path='/category', headers=self.get_header_html())
        assert(rsp.status_code == 200)

    def test_bad_password_auth(self):
        # first register a user
        tu = TestUser()
        tu.create_user()
        rsp = self.post_registration(tu)
        assert (rsp.status_code == 201)

        # now login and get a token
        tu.set_password('dummy password')
        rsp = self.post_auth(tu)
        data = json.loads(rsp.data.decode("utf-8"))
        desc = data['description']
        err = data['error']
        assert (rsp.status_code == 401 and desc == "Invalid credentials" and err == "Bad Request")
        return

    def test_login(self):
        # first create a user
        tu = TestUser()
        tu.create_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)

        # now login and get a token
        rsp = self.post_auth(tu)
        assert(rsp.status_code == 200)
        assert(rsp.content_type == 'application/json')
        data = json.loads(rsp.data.decode("utf-8"))
        token = data['access_token']
        tu.set_token(token)
        self.set_token(token)
            
        return tu

    def test_ballot_no_args(self):
        self.create_testuser_get_token()
        hd=self.get_header_html()
        rsp = self.app.get(path='/ballot', headers=hd)
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('NO_ARGS') and rsp.status_code == 400)

        return rsp

    def test_vote_not_json(self):
        self.create_testuser_get_token()
        rsp = self.app.post(path='/vote', headers=self.get_header_html())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('NO_JSON') and rsp.status_code == 400)

        return rsp

    def test_photo_not_json(self):
        self.create_testuser_get_token()
        rsp = self.app.post(path='/photo', headers=self.get_header_html())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('NO_JSON') and rsp.status_code == 400)

        return rsp

    def test_register_not_json(self):
        rsp = self.app.post(path='/register', headers={'content-type': 'text/html'})
        data = json.loads(rsp.data.decode("utf-8"))
        errormsg = data['msg']
        assert(errormsg == error.error_string('NO_JSON') and rsp.status_code == 400)

        return rsp

    def test_photo_missing_args(self):
        self.create_testuser_get_token()
        rsp = self.app.post(path='/photo', data=json.dumps(dict(image=None, extension=None, category_id=None, user_id=None) ), headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS') and rsp.status_code == 400)

        rsp = self.app.post(path='/photo', data=json.dumps(dict(username='bp100a') ), headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS')and rsp.status_code == 400)

        return rsp

    def test_register_missing_args(self):
        self.create_testuser_get_token()
        rsp = self.app.post(path='/register', data=json.dumps(dict(username=None, password='pa55w0rd') ), headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS') and rsp.status_code == 400)

        rsp = self.app.post(path='/register', data=json.dumps(dict(username='bp100a') ), headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS') and rsp.status_code == 400)

        return rsp

    def test_spec_page(self):
        rsp = self.app.get(path='/spec/swagger.json', headers={'content-type': 'text/html'})
        assert(rsp.status_code == 200)

    def test_root_page(self):
        rsp = self.app.get(path='/config', headers={'content-type': 'text/html'})
        assert(rsp.status_code == 200)

    def test_ballot_empty_args(self):
        self.create_testuser_get_token()
        rsp = self.app.get(path='/ballot', query_string=urlencode({'category_id':None}), headers=self.get_header_html())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS') and rsp.status_code == 400)

    def test_ballot_missing_args(self):
        self.create_testuser_get_token()
        rsp = self.app.get(path='/ballot', query_string=urlencode({'username':'bp100a'}), headers=self.get_header_html())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS') and rsp.status_code == 400)

    def test_vote_missing_args(self):
        self.create_testuser_get_token()
        self.create_testuser_get_token()
        rsp = self.app.post(path='/vote', data=json.dumps(dict(user_id=None, votes=None) ), headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS') and rsp.status_code == 400)

        rsp = self.app.post(path='/vote', data=json.dumps(dict(username='bp100a') ), headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS') and rsp.status_code == 400)

        return rsp

class TestPhotoUpload(iiBaseUnitTest):

    _uid = None
    _cid = None

    def test_anon_user_photo_upload(self):
        self.create_anon_testuser_get_token()
        self.test_photo_upload(self.get_token())
        
    def test_photo_upload(self, token=None):

        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()

        self.setUp()
        if token is None:
            self.create_testuser_get_token() # force token creation
        else:
            self.set_token(token) # use token passed in

        # we have our user, now we need a photo to upload
        ft = open('../photos/Suki.JPG', 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, token=self.get_token())

        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        rsp = self.app.post(path='/photo', data=json.dumps(dict(category_id=cid, extension=ext, image=b64img)),
                            headers=self.get_header_json())

        assert(rsp.status_code == 201)
        data = json.loads(rsp.data.decode("utf-8"))
        filename = data['filename']
        assert(filename is not None)

        # let's read back the filename while we are here
        rsp = self.app.get(path='/image', query_string=urlencode({'filename':filename}),
                           headers=self.get_header_html())

        assert(rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        b64_photo = data['image']
        assert(len(b64_photo) == len(b64img))

        self._cid = cid
        return

    def test_healthcheck(self):
        rsp = self.app.get(path='/healthcheck')
        assert(rsp.status_code == 200)

    def test_image_no_such_file(self):
        self.setUp()
        self.create_testuser_get_token() # force token creation
        filename = uuid.uuid1()
        rsp = self.app.get(path='/image', query_string=urlencode({'filename':filename}),
                           headers=self.get_header_html())
        assert(rsp.status_code == 500)
        data = json.loads(rsp.data.decode('utf-8'))
        msg = data['msg']
        assert(msg == error.error_string('ERROR_PHOTO'))
        return

    def test_image_no_file(self):
        self.setUp()
        self.create_testuser_get_token()  # force token creation
        filename = uuid.uuid1()
        rsp = self.app.get(path='/image', query_string=urlencode({'filename': None}),
                           headers=self.get_header_html())
        assert (rsp.status_code == 400)
        data = json.loads(rsp.data.decode('utf-8'))
        msg = data['msg']
        assert (msg == error.error_string('MISSING_ARGS'))
        return

    def test_image_no_args(self):
        self.setUp()
        self.create_testuser_get_token()  # force token creation
        filename = uuid.uuid1()
        rsp = self.app.get(path='/image', headers=self.get_header_html())
        assert (rsp.status_code == 400)
        data = json.loads(rsp.data.decode('utf-8'))
        msg = data['msg']
        assert (msg == error.error_string('NO_ARGS'))
        return



class TesttVoting(iiBaseUnitTest):

    _uid = None
    def test_ballot_success(self):
        self.get_ballot_by_token(None)
        return

    def ballot_response(self, rsp):
        data = json.loads(rsp.data.decode("utf-8"))

        assert(rsp.status_code == 200)

        ballots = data

        assert(len(ballots) == 4)

        for be_dict in ballots:
            bid = be_dict['bid']
            image = be_dict['image']
            path = "/mnt/image_files/thumb{}.jpeg".format(bid)
            thumbnail = base64.b64decode(image)
            fp = open(path, "wb")
            fp.write(thumbnail)
            fp.close()

        return ballots

    def get_ballot_by_token(self, token=None):
        # let's create a user
        if token is None:
            self.create_testuser_get_token()
        else:
            self.set_token(token)

        # ensure we have a category set to uploading
        cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, token=self.get_token())

        # set category to voting
        rsp = self.app.post(path='/setcategorystate', data=json.dumps(dict(category_id=cid, state=category.CategoryState.UPLOAD.value)),
                            headers=self.get_header_json())
        assert(rsp.status_code == 200)

        # we need to post a set of ballots with votes
        tp = TestPhotoUpload()
        tp.setUp()
        for idx in range(10):
            tp.test_photo_upload(None) # create a user & upload a photo

        # set category to voting
        rsp = self.app.post(path='/setcategorystate', data=json.dumps(dict(category_id=cid, state=category.CategoryState.VOTING.value)),
                            headers=self.get_header_json())

        assert(rsp.status_code == 200)

        rsp = self.app.get(path='/ballot', query_string=urlencode({'category_id':cid}),
                            headers=self.get_header_html())

        return self.ballot_response(rsp)

    def test_ballot_invalid_category_id(self):
        # let's create a user
        self.create_testuser_get_token()
        rsp = self.app.get(path='/ballot', query_string=urlencode({'category_id':0}),
                           headers=self.get_header_html())

        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(rsp.status_code == 500 and emsg == error.iiServerErrors.error_message(error.iiServerErrors.INVALID_CATEGORY) )
        return

    def test_anon_voting(self):

        self.create_anon_testuser_get_token()

        # first make sure we have an uploadable category
        cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, self.get_token())

        ballots = self.get_ballot_by_token(self.get_token()) # read a ballot
        assert(ballots is not None)

        votes = []
        idx = 1
        for be_dict in ballots:
            bid = be_dict['bid']
            if (idx % 2) == 0:
                votes.append(dict({'bid':bid, 'vote':idx, 'like':"true"}))
            else:
                votes.append(dict({'bid': bid, 'vote': idx}))
            idx += 1

        jvotes = json.dumps(dict({'votes':votes}))

        # now switch our category over to voting
        TestCategory().set_category_state(cid, category.CategoryState.VOTING)

        rsp = self.app.post(path='/vote', data=jvotes, headers=self.get_header_json())
        assert(rsp.status_code == 200)
        return self.ballot_response(rsp)

    def test_voting(self):

        self.create_testuser_get_token()

        # first make sure we have an uploadable category
        cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, self.get_token())

        ballots = self.get_ballot_by_token(self.get_token()) # read a ballot
        assert(ballots is not None)

        votes = []
        idx = 1
        for be_dict in ballots:
            bid = be_dict['bid']
            if (idx % 2) == 0:
                votes.append(dict({'bid':bid, 'vote':idx, 'like':"true"}))
            else:
                votes.append(dict({'bid': bid, 'vote': idx}))
            idx += 1

        jvotes = json.dumps(dict({'votes':votes}))

        # now switch our category over to voting
        TestCategory().set_category_state(cid, category.CategoryState.VOTING)

        rsp = self.app.post(path='/vote', data=jvotes, headers=self.get_header_json())
        assert(rsp.status_code == 200)
        return self.ballot_response(rsp)

    def test_voting_one_vote(self):

        self.create_testuser_get_token()

        # first make sure we have an uploadable category
        cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, self.get_token())

        ballots = self.get_ballot_by_token(self.get_token()) # read a ballot
        assert(ballots is not None)

        votes = []
        idx = 1
        for be_dict in ballots:
            bid = be_dict['bid']
            votes.append(dict({'bid':bid, 'vote':1, 'like':"true"}))

        jvotes = json.dumps(dict({'votes':votes}))

        # now switch our category over to voting
        TestCategory().set_category_state(cid, category.CategoryState.VOTING)

        rsp = self.app.post(path='/vote', data=jvotes, headers=self.get_header_json())
        assert(rsp.status_code == 200)
        return self.ballot_response(rsp)

    def test_voting_too_many(self):
        self.create_testuser_get_token()
        ballots = self.get_ballot_by_token(self.get_token()) # read a ballot
        assert(ballots is not None)

        votes = []
        idx = 1
        for be_dict in ballots:
            bid = be_dict['bid']
            if (idx % 2) == 0:
                votes.append(dict({'bid':bid, 'vote':idx, 'like':"true"}))
            else:
                votes.append(dict({'bid': bid, 'vote': idx}))
            idx += 1

        votes.append(dict({'bid':0, 'vote':1, 'like':"true"})) # add extra so we fail!

        jvotes = json.dumps(dict({'votes':votes}))
        rsp = self.app.post(path='/vote', data=jvotes, headers=self.get_header_json())
        assert(rsp.status_code == 413)
        return rsp

    def test_friend_request(self):
        # let's create a user
        self.create_testuser_get_token()
        rsp = self.app.post(path='/friendrequest', data=json.dumps(dict(friend="bp100a@hotmail.com")),
                           headers=self.get_header_json())

        data = json.loads(rsp.data.decode("utf-8"))
        rid = data['request_id']
        assert(rsp.status_code == 201 and data['msg'] == error.error_string('WILL_NOTIFY_FRIEND') and rid != 0)
        return rid

    def test_friend_request_no_arg(self):
        # let's create a user
        self.create_testuser_get_token()
        rsp = self.app.post(path='/friendrequest', data=json.dumps(dict(dummy="bp100a@hotmail.com")),
                           headers=self.get_header_json())

        data = json.loads(rsp.data.decode("utf-8"))
        assert(rsp.status_code == 400 and data['msg'] == error.error_string('MISSING_ARGS'))
        return

    def test_friend_request_no_json(self):
        # let's create a user
        self.create_testuser_get_token()
        rsp = self.app.post(path='/friendrequest', data="no json - no json",
                           headers=self.get_header_html())

        assert(rsp.status_code == 400)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['msg'] == error.d_ERROR_STRINGS['NO_JSON'])

    def test_friend_request_current_user(self):
        # let's create a user
        self.create_testuser_get_token()
        f = TestLogin()
        f.setUp()
        fu = f.test_login()  # this will register (create) and login an user, returning the UID

        # okay we created 2 users, one is asking the other to be a friend and the 2nd is in the system
        rsp = self.app.post(path='/friendrequest',
                            data=json.dumps(dict(friend=fu.get_username())),
                            headers=self.get_header_json())

        data = json.loads(rsp.data.decode("utf-8"))
        rid = data['request_id']
        assert (rsp.status_code == 201 and data['msg'] == error.error_string('WILL_NOTIFY_FRIEND') and rid != 0)
        return dict(request_id=rid, user_id=fu.get_uid())


    def test_friend_request_accepted(self):

        self.create_testuser_get_token()
        d = self.test_friend_request_current_user()    # create a request
        rid = d['request_id']

        # we need to create a friend request
        # okay we created 2 users, one is asking the other to be a friend and the 2nd is in the system
        rsp = self.app.post(path='/acceptfriendrequest',
                            data=json.dumps(dict(request_id=rid, accepted="true")),
                            headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        assert(rsp.status_code == 201)
        assert(data['msg'] == "friendship updated")

    def test_friend_request_accepted_no_json(self):

        self.create_testuser_get_token()
        rsp = self.app.post(path='/acceptfriendrequest',
                            data="no json -- no json",
                            headers=self.get_header_html())

        assert(rsp.status_code == 400)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['msg'] == error.d_ERROR_STRINGS['NO_JSON'])

    def test_friend_request_accepted_missing_arg(self):

        d = self.test_friend_request_current_user()    # create a request
        uid = d['user_id']
        rid = d['request_id']

        # we need to create a friend request
        # okay we created 2 users, one is asking the other to be a friend and the 2nd is in the system
        rsp = self.app.post(path='/acceptfriendrequest',
                            data=json.dumps(dict(user_id=0, accepted="true")),
                            headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        assert(rsp.status_code == 400)
        assert(data['msg'] == error.d_ERROR_STRINGS['MISSING_ARGS'])



class TestCategory(iiBaseUnitTest):

    _cl = None

    def test_category_state_no_json(self):

        self.create_testuser_get_token()
        rsp = self.app.post(path='/setcategorystate', data='not json - not json',
                            headers=self.get_header_html())

        assert(rsp.status_code == 400)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['msg'] == error.d_ERROR_STRINGS['NO_JSON'])

    def test_category_state_no_cid(self):
        self.create_testuser_get_token()
        cstate = category.CategoryState.UPLOAD.value
        rsp = self.app.post(path='/setcategorystate', data=json.dumps(dict(state=cstate)),
                            headers=self.get_header_json())

        assert(rsp.status_code == 400)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['msg'] == error.d_ERROR_STRINGS['MISSING_ARGS'])

    def test_category_state_bad_cid(self):
        self.create_testuser_get_token()
        cstate = category.CategoryState.UPLOAD.value
        rsp = self.app.post(path='/setcategorystate', data=json.dumps(dict(category_id=0, state=cstate)),
                            headers=self.get_header_json())

        assert (rsp.status_code == 400)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['msg'] == 'invalid category')

    def test_category_state(self):
        # let's create a user
        self.create_testuser_get_token()

        cid = 1
        cstate = category.CategoryState.UPLOAD.value
        rsp = self.app.post(path='/setcategorystate', data=json.dumps(dict(category_id=cid, state=cstate)),
                            headers=self.get_header_json())

        assert(rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        msg = data['msg']
        assert(msg == error.error_string('CATEGORY_STATE') or msg == error.iiServerErrors.error_message(error.iiServerErrors.NO_STATE_CHANGE) )

    def set_category_state(self, cid, target_state):
        # let's create a user
        tu = self.create_testuser_get_token()

        rsp = iiServer.app.test_client().post(path='/setcategorystate', data=json.dumps(dict(category_id=cid, state=target_state.value)),
                            headers=self.get_header_json())

        assert(rsp.status_code == 200)

    def read_category(self, token):
        # let's create a user
        if token is None:
            tu = self.create_testuser_get_token()
        else:
            self.set_token(token)

        rsp =  iiServer.app.test_client().get(path='/category',headers=self.get_header_html())

        assert(rsp.status_code == 200)

        data = json.loads(rsp.data.decode("utf-8"))
        return data

    def get_category_by_state(self, target_state, token):

        cl = self.read_category(None)
        assert(cl is not None)

        for c in cl:
            state = c['state']
            cid = c['id']
            desc = c['description']
            if state == target_state.value:
                return cid

        # we didn't find an upload category, set the first one to upload
        c = cl[0]
        cid = c['id']
        rsp = iiServer.app.test_client().post(path='/setcategorystate', data=json.dumps(dict(category_id=cid, state=target_state.value)),
                            headers=self.get_header_json())
        assert(rsp.status_code == 200)
        return cid

    def test_category(self):
        # let's create a user
        tu = self.create_testuser_get_token()

        rsp = self.app.get(path='/category', headers=self.get_header_html())
        assert(rsp.status_code == 200)

        cl = json.loads(rsp.data.decode("utf-8"))
        assert(len(cl) != 0)

        # verify that all keys are in the dictionary returned
        keylist = ('state', 'round', 'start', 'end', 'id', 'theme')
        for key in keylist:
            assert(key not in cl)
        return

class TestLeaderBoard(iiBaseUnitTest):

    _photos = ['Cute_Puppy.jpg',
              'Emma Passport.jpg',
              'Galaxy Edge 7 (full res)jpg.jpg',
              'Galaxy Edge 7 Cat  (full res)jpg.jpg',
              'Galaxy Edge 7 Office Desk (full res, hdr).jpg',
              'Hawaii Palm Tree.JPG',
              'iPhone 6 Spider web (full res).JPG',
              'iPhone 7 statue and lake (full res).jpg',
              'iPhone 7 Yellow Rose (full res).jpg',
              'Netsoft USA Company Picture 1710.jpg',
              'PrimRib.JPG',
              'Suki.JPG',
              'Turtle.JPG',
               'Portrait.JPG',
               'Rotate90CW.JPG',
               'Rotate180CW.JPG',
               'Rotate270CW.JPG',

               '2012-05-23 19.45.55.jpg',
               '20130826_170610_A.jpg',
               'img_0264_edited-100686951-orig.jpg',
               'img_0026.jpg',
               'img_0034.jpg',
               'apple-iphone-7-camera-samples-27.jpg',
               'Apple-iPhone-7-camera-photo-sample-2.jpg',
               'iphone-7-plus-camera-trout.jpg',
               'IMG_0307.JPG',
               'iPhone-7-Camera-AndyNicolaides.jpg',
               'img_0017.jpg',
               '9lqqdnm.jpg',
               '001-B-Moto-Z-Force-Droid-Samples.jpg',
               'moto-z-play-camera-sample.jpg',
               'moto_z_play_camera_samples_7.jpg',
               'sample1.jpg',
               'Moto-Z-Force-Droid.jpg',
               'tf2fzhr.jpg',
               'IMG_1218.JPG',
               'sam_4089.jpg',
               'vetndhl.jpg'
               ]

    _users = {'hcollins@gmail.com',
              'bp100a@hotmail.com',
              'dblankley@blankley.com',
              'regcollins@hotmail.com',
              'qaetre@hotmail.com',
              'hcollins@prizepoint.com',
              'hcollins@exit15w.com',
              'harry.collins@epam.com',
              'crazycow@netsoft-usa.com',
              'harry.collins@netsoft-usa.com',
              'hcollins@altaitech.com',
              'dblankley@uproar.com',
              'rcollins@exit15w.com',
              'harry.collins@exit15w.com',
              'admin@prizepoint.com',
              'hcollins@pointcast.com'}

    _base_url = None

    def test_leaderboard_no_args(self):
        self.create_testuser_get_token()
        rsp = self.app.get(path='/leaderboard', headers=self.get_header_html())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('NO_ARGS') and rsp.status_code == 400)

        return rsp

    def test_leaderboard_missing_args(self):
        self.create_testuser_get_token()
        rsp = self.app.get(path='/leaderboard', query_string=urlencode({'category_id':None}), headers=self.get_header_html())
        data = json.loads(rsp.data.decode("utf-8"))
        emsg = data['msg']
        assert(emsg == error.error_string('MISSING_ARGS') and rsp.status_code == 400)

        return rsp

    def upload_photo(self, tu, photo_name):

        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()

        # we have our user, now we need a photo to upload
        fn = '../photos/' + photo_name
        ft = open(fn, 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        # okay, we need to post this
        cid = tu.get_cid()
        self.set_token(tu.get_token())
        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        rsp = self.app.post(path='/photo', data=json.dumps(dict(category_id=cid, extension=ext, image=b64img)),
                            headers=self.get_header_json())
        assert (rsp.status_code == 201)
        return

    def get_ballot_by_user(self, tu):
        assert(tu is not None)
        assert(tu.get_token() is not None)
        self.set_token(tu.get_token())
        rsp = self.app.get(path='/ballot', query_string=urlencode({'category_id':tu.get_cid()}),
                            headers=self.get_header_html())

        data = json.loads(rsp.data.decode("utf-8"))
        assert(rsp.status_code == 200)
        ballots = data
        assert(len(ballots) < 5)
        return ballots

    def vote_ballot(self, tu, ballots):
        if ballots is None or len(ballots) == 0:
            return

        votes = []
        idx = 1
        for be_dict in ballots:
            bid = be_dict['bid']
            if (idx % 2) == 0:
                votes.append(dict({'bid':bid, 'vote':idx, 'like':"true"}))
            else:
                votes.append(dict({'bid': bid, 'vote': idx}))
            idx += 1

        jvotes = json.dumps(dict({'votes':votes}))

        rsp = self.app.post(path='/vote', data=jvotes, headers=self.get_header_json())
        assert(rsp.status_code == 200)
        return

    def get_leaderboard(self, tu):
        assert(tu is not None)

        rsp = self.app.get(path='/leaderboard', query_string=urlencode({'category_id':tu.get_cid()}),
                            headers=self.get_header_html())

        lb = json.loads(rsp.data.decode("utf-8"))
        assert(rsp.status_code == 200)
        return lb

    def test_leaderboard(self):
        self.setUp()

        # okay, this will get complex. We have to do the following:

        # setup a category for Uploading
        # register a bunch of users
        # upload photos for those users
        # download ballots for some of the users
        # vote a bunch of times
        # download the leaderboard
        # okay, we're going to create users & upload photos
        user_list = []
        cid = None
        for uname in self._users:
            tu = self.create_testuser_get_token()
            if cid is None:
                cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, token=tu.get_token())
            tu.set_cid(cid)
            user_list.append(tu)

        # only upload a single photo in the category
        # for each user
        num_photos = len(self._photos)
        photo_idx = 0
        for tu in user_list:
            self.upload_photo(tu, self._photos[photo_idx])
            photo_idx += 1
            if photo_idx > num_photos:
                photo_idx = 0

        # okay we've uploaded a bunch of users and gave them photos


        # set the category to VOTING
        TestCategory().set_category_state(tu.get_cid(), category.CategoryState.VOTING)

        # now we need to do some voting
        for tu in user_list:
            b = self.get_ballot_by_user(tu)
            self.vote_ballot(tu, b)

        # now let's get the leaderboard
        for tu in user_list:
            lb = self.get_leaderboard(tu)
            for l in lb:
                img = l['image']
                rank = l['rank']
                score = l['score']



class TestLastSubmission(iiBaseUnitTest):

    def test_last_submission_no_submissions(self):
        self.setUp()
        self.create_testuser_get_token()
        rsp = self.app.get(path='/lastsubmission', headers=self.get_header_html())
        data = json.loads(rsp.data.decode("utf-8"))
        assert (json.loads(rsp.data.decode("utf-8"))['msg'] == error.error_string('NO_SUBMISSION') and rsp.status_code == 200)

    def test_last_submission(self):
        self.setUp()
        self.create_testuser_get_token()
        tp = TestPhotoUpload()

        tp.test_photo_upload(self.get_token())  # creates user, uploads a photo and downloads it again

        rsp = self.app.get(path='/lastsubmission', headers=self.get_header_html())
        assert(rsp.status_code == 200)

        data = json.loads(rsp.data.decode("utf-8"))
        try:
            last_image = data['image']
            category = data['category']
        except KeyError:
            self.Fail()

        assert (rsp.status_code == 200)



