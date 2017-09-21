import os
import unittest
import uuid
import hashlib
import iiServer
import json
import base64
import datetime
from models import category, resources, voting, photo
from collections import namedtuple
import requests
from models import error
from urllib.parse import urlencode
from werkzeug.datastructures import Headers, FileMultiDict
import dbsetup
from models import admin, usermgr
from tests import DatabaseTest
from models import photo
from sqlalchemy import func
from controllers import categorymgr

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
        self._g = self._u
        return

    def is_anonuser(self):
        return self._g == self._u

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


    def get_header_authorization(self):
        assert(self.get_token() is not None)
        headers = Headers()
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

    def post_cors_auth(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        rsp = self.app.post(path='/cors_auth', data=json.dumps(dict(username=u, password=p)),
                            headers={'content-type': 'application/json'})
        return rsp
    def post_registration(self, tu):
        u = tu.get_username()
        p = tu.get_password()
        g = tu.get_guid()
        rsp = self.app.post(path='/register', data=json.dumps(dict(username=u, password=p, guid=g)), headers={'content-type': 'application/json'})
        return rsp

    def make_user_IISTAFF(self, tu):
        """
        make_user_iistaff() - sets usertype field so this user can call privileged services
        :param emailaddres:
        :return:
        """
        session = dbsetup.Session()
        if not tu.is_anonuser():
            u = usermgr.User.find_user_by_email(session, tu.get_username())
            au = usermgr.AnonUser.get_anon_user_by_id(session, u.id)
        else:
            au = usermgr.AnonUser.find_anon_user(session, tu._g)

        au.usertype = usermgr.UserType.IISTAFF.value
        session.add(au)
        session.commit()

    def create_testuser_get_token(self, make_staff=True):
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

        if make_staff:
            self.make_user_IISTAFF(tu)
        return tu

    def create_anon_testuser_get_token(self, make_staff=False):
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

        # see if we need to turn this user into a stff member
        if make_staff:
            self.make_user_IISTAFF(tu)
        return tu

    def get_user_id(self,session, tu) -> int:

        au = usermgr.AnonUser.find_anon_user(session, tu.get_guid())
        assert(au is not None)
        return au.id

    def upload_photo_to_category(self, c:category.Category):

        # we have our user, now we need a photo to upload
        # read our test file
        cwd = os.getcwd()
        if 'tests' in cwd:
            path = '../photos/TestPic.JPG' #'../photos/Cute_Puppy.jpg'
        else:
            path = cwd + '/photos/TestPic.JPG' #'/photos/Cute_Puppy.jpg'
        ft = open(path, 'rb')
        ph = ft.read()
        ft.close()

        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        rsp = self.app.post(path='/photo', data=json.dumps(dict(category_id=c.id, extension=ext, image=b64img)),
                            headers=self.get_header_json())
        assert(rsp.status_code == 201 or rsp.status_code == 200)

    def create_test_categories_with_photos(self, session, num_categories: int, num_photos: int) -> (list, list):
        u_staff = self.create_testuser_get_token(make_staff=True)  # get a user so we can use the API

        open_cl = []
        for i in range(0, num_categories):
            category_name = 'TestUserLike{0}'.format(i)
            dt_start = categorymgr.CategoryManager.next_category_start(session)
            start_date = dt_start.strftime("%Y-%m-%d %H:%M")
            cm = categorymgr.CategoryManager(description=category_name, start_date=start_date, upload_duration=24, vote_duration=24)
            c = cm.create_category(session, type=category.CategoryType.OPEN.value)
            session.commit()
            session.add(c)
            open_cl.append(c)

        session.commit()

        # all these categories are in the PENDING state
        # let's change them to upload and upload some photos to them
        for c in open_cl:
            c.state = category.CategoryState.UPLOAD.value
            session.add(c)

        session.commit() # flush everything to the DB

        # we now have categories that will accept a photo
        self.set_token(u_staff.get_token())
        for c in open_cl:
            for i in range(0, num_photos):
                self.upload_photo_to_category(c)

        u_staff._uid = self.get_user_id(session, u_staff)
        session2 = dbsetup.Session()
        q = session2.query(photo.Photo).filter(photo.Photo.user_id == u_staff._uid)
        pl = q.all()
        session2.close()
        return (pl, open_cl)

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

    def test_cors_auth(self):
        # first register a user
        tu = TestUser()
        tu.create_user()
        rsp = self.post_registration(tu)
        assert(rsp.status_code == 201)

        # now login and get a token
        rsp = self.post_cors_auth(tu)
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
        assert(rsp.status_code == 200)

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

    def test_oAuth2_FAKESERVICEPROVIDER(self):
        rsp = self.app.post(path='/auth', data=json.dumps(dict(username='FAKESERVICEPROVIDER', password='token')),
                            headers={'content-type': 'application/json'})

        assert(rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['email'] == 'fakeuser@fakeserviceprovider.com')

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
        ft = open('../photos/TEST1.JPG', 'rb')
        assert (ft is not None)
        ph = ft.read()
        ft.close()
        assert (ph is not None)

        cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, token=self.get_token())

        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        rsp = self.app.post(path='/photo', data=json.dumps(dict(category_id=cid, extension=ext, image=b64img)),
                            headers=self.get_header_json())

        assert(rsp.status_code == 201 or rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        if rsp.status_code == 201:
            filename = data['filename']
            assert(filename is not None)
            # let's read back the filename while we are here
            rsp = self.app.get(path='/image', query_string=urlencode({'filename': filename}),
                               headers=self.get_header_html())

            assert (rsp.status_code == 200)
            data = json.loads(rsp.data.decode("utf-8"))
            b64_photo = data['image']
            assert (len(b64_photo) == len(b64img))
        else:
            ballots = data['ballots']
            if len(ballots) != 4:
                assert (False)
            assert (len(ballots) == 4)


        self._cid = cid
        return

    def test_binary_upload_no_image(self, token=None):
        self.setUp()
        if token is None:
            self.create_testuser_get_token() # force token creation
        else:
            self.set_token(token) # use token passed in

        cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, token=self.get_token())
        ext = 'JPEG'
        rsp = self.app.post(path='/jpeg/{0}'.format(cid), headers=self.get_header_authorization(), content_type='image/jpeg', data=None)
        assert(rsp.status_code == 400)
        self.tearDown()

    def test_binary_upload(self, token=None):
        '''
        upload a binary JPEG file to the server
        :param token:
        :return:
        '''
        dir_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()

        self.setUp()
        if token is None:
            self.create_testuser_get_token() # force token creation
        else:
            self.set_token(token) # use token passed in

        cid = TestCategory().get_category_by_state(category.CategoryState.UPLOAD, token=self.get_token())

        # we have our user, now we need a photo to upload
        ft = open('../photos/TEST1.JPG', mode='rb')
        assert (ft is not None)
        ph = ft.read()
        ft.close()
        assert (ph is not None)
        files = {'photo': ph}

#        rsp = self.app.request(method='POST', url='/jpeg/{0}'.format(cid), files=files, headers=self.get_header_authorization())
        rsp = self.app.post(path='/jpeg/{0}'.format(cid), headers=self.get_header_authorization(), data=ph, content_type='image/jpeg')

        assert(rsp.status_code == 201 or rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        if rsp.status_code == 201:
            filename = data['filename']
            assert(filename is not None)
            # let's read back the filename while we are here
            rsp = self.app.get(path='/image', query_string=urlencode({'filename': filename}),
                               headers=self.get_header_html())

            assert (rsp.status_code == 200)
            data = json.loads(rsp.data.decode("utf-8"))
            b64_photo = data['image']
            assert (len(b64_photo) == len(b64img))
        else:
            ballots = data['ballots']
            if len(ballots) != 4:
                assert (False)
            assert (len(ballots) == 4)

        self._cid = cid
        self.tearDown()
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

class TestImages(iiBaseUnitTest):

    def test_preview_bad_method(self):
        headers = Headers()
        headers.add('content-type', 'text/html')
        headers.add('User-Agent', 'Python Tests')
        rsp = self.app.post(path='/preview/0', headers=headers)
        assert(rsp.status_code == 405)

    def test_preview_bad_pid(self):
        headers = Headers()
        headers.add('content-type', 'text/html')
        headers.add('User-Agent', 'Python Tests')
        rsp = self.app.get(path='/preview/0', headers=headers)
        assert(rsp.status_code == 404)

    def get_valid_photo_id(self, session):

        fo = photo.Photo()
        pi = photo.PhotoImage()
        pi._extension = 'JPEG'

        # read our test file
        cwd = os.getcwd()
        if 'tests' in cwd:
            path = '../photos/SAMSUNG2.JPG' #'../photos/Cute_Puppy.jpg'
        else:
            path = cwd + '/photos/SAMSUNG2.JPG' #'/photos/Cute_Puppy.jpg'
        ft = open(path, 'rb')
        pi._binary_image = ft.read()
        ft.close()

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        c.state = category.CategoryState.UPLOAD.value
        session.commit()

        # create a user
        guid = str(uuid.uuid1())
        anon_username = guid.upper().translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(session, anon_username)
        assert(au is not None)
        session.commit()

        fo.category_id = c.id
        d = fo.save_user_image(session, pi, au.id, c.id)
        assert(d['error'] is None)
        fn = fo.filename
        session.commit() # Photo & PhotoMeta should be written out

        pid = fo.id

        c.state = category.CategoryState.CLOSED.value
        session.commit()
        return pid

    def test_preview_good_pid(self):
        headers = Headers()
        headers.add('content-type', 'text/html')
        headers.add('User-Agent', 'Python Tests')

        session = dbsetup.Session()
        pid = self.get_valid_photo_id(session)
        rsp = self.app.get(path='/preview/{0}'.format(pid), headers=headers)

        session.rollback()
        session.close()
        if rsp.status_code != 200:
            print("[test_preview_good_pid] HTTP response status = {} for pid {}".format(rsp.status_code, pid))
            assert(False)
        assert(rsp.status_code == 200)
        assert(rsp.content_type == 'image/jpeg')
        assert(rsp.content_length > 30000)


class TestLogging(iiBaseUnitTest):

    def test_log_event(self):
        self.create_testuser_get_token()
        rsp = self.app.post(path='/log', data=json.dumps(dict(msg='Test logging message')), headers=self.get_header_json())

        data = json.loads(rsp.data.decode("utf-8"))
        assert(rsp.status_code == 200)

class TesttVoting(iiBaseUnitTest):

    _uid = None
    def test_ballot_success(self):
        self.get_ballot_by_token(None)
        return

    def ballot_response(self, rsp):
        data = json.loads(rsp.data.decode("utf-8"))

        assert(rsp.status_code == 200)
        ballots = data['ballots']
        if len(ballots) != 4:
            assert(False)
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
            self.create_testuser_get_token(make_staff=True)
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
        assert('msg' in data.keys())
        emsg = data['msg']
        assert(rsp.status_code == 500 and emsg == error.error_string('NO_BALLOT') )
        return

    def test_create_category_next_start(self):
        self.create_anon_testuser_get_token(make_staff=True)

        # create category information
        d_data = {'start_date': 'next', 'upload': 24, 'voting': 72, 'name': 'TESTCategory'}
        j_category = json.dumps(d_data)
        rsp = self.app.post(path='/category', data=j_category,headers=self.get_header_json())
        assert(rsp.status_code == 201)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['category']['description'] == 'TESTCategory')

    def test_create_category_bad_start(self):
        self.create_anon_testuser_get_token(make_staff=True)

        # create category information
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:S")
        d_data = {'start_date': start_date, 'upload': 24, 'voting': 72, 'name': 'CreateCategoryBadDate'}
        j_category = json.dumps(d_data)
        rsp = self.app.post(path='/category', data=j_category,headers=self.get_header_json())
        assert(rsp.status_code == 400)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['msg'] == error.error_string('BAD_DATEFORMAT'))

    def test_create_category_early_start(self):
        self.create_anon_testuser_get_token(make_staff=True)

        # create category information
        start_date = (datetime.datetime.now() - datetime.timedelta(days=1) ).strftime("%Y-%m-%d %H:%M")
        d_data = {'start_date': start_date, 'upload': 24, 'voting': 72, 'name': 'CreateCategoryEarlyDate'}
        j_category = json.dumps(d_data)
        rsp = self.app.post(path='/category', data=j_category,headers=self.get_header_json())
        assert(rsp.status_code == 400)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['msg'] == error.error_string('TOO_EARLY'))

    def test_create_category_good_start(self):
        self.create_anon_testuser_get_token(make_staff=True)

        # create category information
        start_date = (datetime.datetime.now() + datetime.timedelta(days=1) ).strftime("%Y-%m-%d %H:%M")
        d_data = {'start_date': start_date, 'upload': 24, 'voting': 72, 'name': 'CreateCategoryGoodDate'}
        j_category = json.dumps(d_data)
        rsp = self.app.post(path='/category', data=j_category,headers=self.get_header_json())
        assert(rsp.status_code == 201)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['category']['description'] == 'CreateCategoryGoodDate')

    def test_anon_voting(self):

        self.create_anon_testuser_get_token(make_staff=True)

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

    def test_friend_request_bogus_accepted(self):

        self.create_testuser_get_token()
        d = self.test_friend_request_current_user()    # create a request
        rid = d['request_id']

        # we need to create a friend request
        # okay we created 2 users, one is asking the other to be a friend and the 2nd is in the system
        rsp = self.app.post(path='/acceptfriendrequest',
                            data=json.dumps(dict(request_id=rid+1, accepted="true")),
                            headers=self.get_header_json())
        data = json.loads(rsp.data.decode("utf-8"))
        assert(rsp.status_code == 500)
        assert(data['msg'] == error.error_string('NO_SUCH_FRIEND'))

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

        assert (rsp.status_code == 500)
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['msg'] == error.error_string('UNKNOWN_ERROR'))

    def test_category_state_valid_category(self):
        # let's create a user
        self.create_testuser_get_token()

        # create a category for us to use
        session = dbsetup.Session()
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72,
                                         description="SetCategoryTesting")
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()
        cid = c.id
        session.close()

        cstate = category.CategoryState.UPLOAD.value
        rsp = self.app.post(path='/setcategorystate', data=json.dumps(dict(category_id=cid, state=cstate)),
                            headers=self.get_header_json())

        assert(rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        msg = data['msg']
        assert(msg == error.error_string('CATEGORY_STATE') )

        cstate = category.CategoryState.UPLOAD.value
        rsp = self.app.post(path='/setcategorystate', data=json.dumps(dict(category_id=cid, state=cstate)),
                            headers=self.get_header_json())

        session.close()
        assert (rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        msg = data['msg']
        assert (msg == error.iiServerErrors.error_message(error.iiServerErrors.NO_STATE_CHANGE))

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

    _photos = ['TEST1.JPG', 'TEST2.JPG', 'TEST3.JPG', 'TEST4.JPG', 'TEST5.JPG', 'TEST6.JPG', 'TEST7.JPG', 'TEST8.JPG', 'SAMSUNG_EXIF.JPG'
               ]

    _users = {'hcollins@gmail.com',
              'bp100a@hotmail.com',
              'dblankley@blankley.com',
              'regcollins@hotmail.com',
              'qaetre@hotmail.com',
#              'hcollins@prizepoint.com',
#              'hcollins@exit15w.com',
#              'harry.collins@epam.com',
#              'crazycow@netsoft-usa.com',
#              'harry.collins@netsoft-usa.com',
#              'hcollins@altaitech.com',
#              'dblankley@uproar.com',
#              'rcollins@exit15w.com',
#              'harry.collins@exit15w.com',
#              'admin@prizepoint.com',
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
        ft.close()

        # okay, we need to post this
        cid = tu.get_cid()
        self.set_token(tu.get_token())
        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        rsp = self.app.post(path='/photo', data=json.dumps(dict(category_id=cid, extension=ext, image=b64img)),
                            headers=self.get_header_json())
        if rsp.status_code != 201 and rsp.status_code != 200:
            rsp = self.app.post(path='/photo', data=json.dumps(dict(category_id=cid, extension=ext, image=b64img)),
                                headers=self.get_header_json())

        if rsp.status_code != 201 and rsp.status_code != 200:
            assert(False)
        assert (rsp.status_code == 201 or rsp.status_code == 200)
        return

    def get_ballot_by_user(self, tu):
        assert(tu is not None)
        assert(tu.get_token() is not None)
        self.set_token(tu.get_token())
        rsp = self.app.get(path='/ballot', query_string=urlencode({'category_id':tu.get_cid()}),
                            headers=self.get_header_html())

        data = json.loads(rsp.data.decode("utf-8"))
        if rsp.status_code != 200:
            assert(rsp.status_code == 200)

        assert(rsp.status_code == 200)
        ballots = data['ballots']
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
        for tu in user_list:
            for i in range(1,10):
                self.upload_photo(tu, 'TestPic.JPG')

        # okay we've uploaded a bunch of users and gave them photos


        # set the category to VOTING
        TestCategory().set_category_state(tu.get_cid(), category.CategoryState.VOTING)

        # we need to create the leaderboard
        tm = categorymgr.TallyMan()
        session = dbsetup.Session()
        c = category.Category().read_category_by_id(tu.get_cid(), session)
        tm.leaderboard_exists(session, c) # this forms connections to Redis
        lb = tm.get_leaderboard_by_category(session, c, check_exist=False)
        lb.rank_member(0, 0, 0) # create dummy entry to spur leaderboard creation

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

        self.tearDown()

class TestMySubmissions(iiBaseUnitTest):

    def test_mysubmissions_bad_format(self):
        self.create_testuser_get_token()
        rsp = self.app.get(path='/submissions', headers=self.get_header_html())
        assert (rsp.status_code == 400)

        rsp = self.app.get(path='/submissions/bad1', headers=self.get_header_html())
        assert (rsp.status_code == 404)

        rsp = self.app.get(path='/submissions/bad2/0', headers=self.get_header_html())
        assert (rsp.status_code == 400)


    def test_mysubmissions_next(self):
        self.create_testuser_get_token()
        rsp = self.app.get(path='/submissions/next/0', headers=self.get_header_html())
        assert (rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        try:
            user_id = data['user']['id']
            created_date = data['user']['created_date']
            assert(user_id is not None and created_date is not None)
        except KeyError as ke:
            assert(False)

    def test_mysubmissions_prev(self):
        self.create_testuser_get_token()
        rsp = self.app.get(path='/submissions/prev/0', headers=self.get_header_html())
        assert (rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        try:
            user_id = data['user']['id']
            created_date = data['user']['created_date']
            assert(user_id is not None and created_date is not None)
        except KeyError as ke:
            assert(False)

class TestBase(iiBaseUnitTest):
    def test_default_base_url(self):
        '''
        we expect the standard URL base to be returned since
        this is a new user with no mapping...
        :return:
        '''
        self.create_testuser_get_token()
        rsp = self.app.get(path='/base', headers=self.get_header_html())
        assert (rsp.status_code == 200)
        assert (rsp.content_type == 'application/json')
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['base'] == 'https://api.imageimprov.com/')

    def test_special_base_url(self):
        '''
        we will create a "base url" and map it to our created user
        :return:
        '''
        self.setUp()

        tu = self.create_testuser_get_token()
        b = admin.BaseURL()
        b.url = 'http://172.21.3.54:8080/'
        session = dbsetup.Session()
        session.add(b)
        session.commit()
        base_id = b.id

        # now update the AnonUser record
        u = usermgr.User.find_user_by_email(session, tu.get_username())
        assert(u is not None)
        au = usermgr.AnonUser.get_anon_user_by_id(session, u.id)
        assert(au is not None)
        au.base_id = b.id
        session.add(au)
        session.commit()

        rsp = self.app.get(path='/base', headers=self.get_header_html())
        assert (rsp.status_code == 200)
        assert (rsp.content_type == 'application/json')
        data = json.loads(rsp.data.decode("utf-8"))
        assert(data['base'] == b.url)

        self.tearDown()

class TestTraction(iiBaseUnitTest):

    def get_headers(self):
        headers = Headers()
        headers.add('content-type', 'text/html')
        headers.add('User-Agent', 'Python Tests')
        return headers

    def test_landing_page(self):
        rsp = self.app.get(path='/play/harry', headers=self.get_headers())
        assert(rsp.status_code == 302)

    def test_landing_page_nocampaign(self):
        rsp = self.app.get(path='/play', headers=self.get_headers())
        assert(rsp.status_code == 302)

    def test_beta1_landing_page_nocampaign(self):
        rsp = self.app.get(path='/beta1', headers=self.get_headers())
        assert(rsp.status_code == 302)
        c = rsp.data.decode("utf-8")
        assert(c.find('campaign=beta1') != -1)

    def test_beta2_landing_page_nocampaign(self):
        rsp = self.app.get(path='/beta2', headers=self.get_headers())
        assert(rsp.status_code == 302)
        c = rsp.data.decode("utf-8")
        assert(c.find('campaign=beta2') != -1)

    def test_beta3_landing_page_nocampaign(self):
        rsp = self.app.get(path='/beta3', headers=self.get_headers())
        assert(rsp.status_code == 302)
        c = rsp.data.decode("utf-8")
        assert(c.find('campaign=beta3') != -1)

    def test_forgotpassword_noemail(self):
        rsp = self.app.get(path='/forgotpwd', query_string=urlencode({'email':None}))
        assert(rsp.status_code == 404)

    def test_forgotpassword_bogusemail(self):
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        bogusemail = guid + '@hotmail.com'
        rsp = self.app.get(path='/forgotpwd', query_string=urlencode({'email':bogusemail}))
        assert(rsp.status_code == 404)

    def test_forgotpassword_legit_email(self):

        tu = self.create_testuser_get_token()
        rsp = self.app.get(path='/forgotpwd', query_string=urlencode({'email':tu.get_username()}))
        assert(rsp.status_code == 200)

    def test_resetpassword_legit_email(self):
        tu = self.create_testuser_get_token()
        rsp = self.app.get(path='/forgotpwd', query_string=urlencode({'email':tu.get_username()}))
        assert(rsp.status_code == 200)

        # okay a password link has been sent out, go to the database and get the CSRF token
        session = dbsetup.Session()
        u = usermgr.User.find_user_by_email(session, tu.get_username())
        assert(u is not None)
        q = session.query(admin.CSRFevent).filter(admin.CSRFevent.user_id == u.id).filter(admin.CSRFevent.been_used == False)
        csrf_list = q.all()
        assert(csrf_list is not None)
        assert(len(csrf_list) > 0)
        csrf = csrf_list[0]
        assert(csrf is not None)

        old_password = u.hashedPWD

        rsp = self.app.post(path='/resetpwd', query_string=urlencode({'pwd': 'pa55w0rd', 'token': csrf.csrf}))
        assert(rsp.status_code == 200)

        session.close()
        session = dbsetup.Session()
        # refetch the user (.expire & .refresh didn't seem to work ??)
        u = usermgr.User.find_user_by_email(session, tu.get_username())
        assert(u.hashedPWD != old_password)
        session.close()

class TestCategoryFiltering(iiBaseUnitTest):

    def create_open_categories(self, session, num_categories: int) -> list:
        cl = []
        for i in range(0, num_categories):
            start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            category_description = "TestingCategory{0}".format(i)
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
            c = cm.create_category(session, category.CategoryType.OPEN.value)
            cl.append(c)

        session.commit()
        return cl

    def close_existing_categories(self, session):

        q = session.query(category.Category). \
            filter(category.Category.state != category.CategoryState.CLOSED.value). \
            update({category.Category.state: category.CategoryState.CLOSED.value})
        session.commit()

    def create_newevent_and_categories(self, session, tu=None) -> str:
        """
        Testing that we can create an event and the categories
        generated will only be visible to the user that created
        the event.
        :return:
        """

        self.close_existing_categories(session)
        open_cl = self.create_open_categories(session, num_categories=3)

        # Step 1 - create test user (if not passed in)
        if tu is None:
            tu = self.create_testuser_get_token(make_staff=False)
        else:
            self.set_token(tu.get_token())

        # # Step 2 - get current categories
        # rsp = self.app.get(path='/category', headers=self.get_header_html())
        # assert(rsp.status_code == 200)
        # category_data = json.loads(rsp.data.decode("utf-8"))

        # Step 3 - create event
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        new_categories = ['Team', 'Success', 'Fun']
        d = {'categories' : new_categories,'num_players': 5, 'start_time': start_date, 'upload_duration': 24, 'voting_duration': 72, 'event_name': 'Image Improv Test'}
        json_data = json.dumps(d)
        rsp = self.app.post(path='/newevent', data=json_data, headers=self.get_header_json())
        assert(rsp.status_code == 201)
        event_details = json.loads(rsp.data.decode('utf-8'))
        accesskey = event_details['accesskey']
        assert(len(accesskey) == 9)
        cl = event_details['categories']
        assert(cl is not None)
        assert(len(cl) == len(new_categories))
        session.close()
        return (event_details, open_cl)

    def test_newevent(self):
        session = dbsetup.Session()
        event_details = self.create_newevent_and_categories(session)
        assert(event_details is not None)
        session.close()

    def test_joinevent(self):
        session = dbsetup.Session()
        event_details, open_cl = self.create_newevent_and_categories(session)
        session.close()
        assert(event_details is not None)
        accesskey = event_details['accesskey']
        assert(accesskey is not None)
        assert(len(accesskey) == 9)

        # Step 1 - create test user
        self.create_testuser_get_token(make_staff=False)

        # Step 2 - join
        query_string = urlencode({'accesskey': accesskey})
        rsp = self.app.post(path='/joinevent', query_string=query_string, headers=self.get_header_html())
        assert(rsp.status_code == 200)
        event_details = json.loads(rsp.data.decode("utf-8"))
        cl = event_details['categories']
        assert(len(cl) == 3)
        assert(event_details['accesskey'] == accesskey)

    def test_event_list(self):

        # okay, we need to create an event and get it back
        session = dbsetup.Session()
        tu = self.create_testuser_get_token()
        self.create_newevent_and_categories(session, tu)
        session.close()
        rsp = self.app.get(path='/event', headers=self.get_header_html())
        assert(rsp.status_code == 200)
        event_list = json.loads(rsp.data.decode("utf-8"))
        assert(event_list is not None)

    def test_event_details(self):

        # okay, we need to create an event and get it back
        tu = self.create_testuser_get_token()
        session = dbsetup.Session()
        self.create_newevent_and_categories(session, tu)
        session.close()
        rsp = self.app.get(path='/event', headers=self.get_header_html())
        assert(rsp.status_code == 200)
        event_list = json.loads(rsp.data.decode("utf-8"))
        assert(event_list is not None)
        assert(len(event_list) == 1)

        event_id = event_list[0]['id']

        rsp = self.app.get(path='/event/{0}'.format(event_id), headers=self.get_header_html())
        assert(rsp.status_code == 200)
        event_details = json.loads(rsp.data.decode("utf-8"))
        cl = event_details['categories']
        assert(len(cl) == 3)
        assert(event_details['id'] == event_id)

    def upload_photo_to_category(self, c:category.Category):

        # we have our user, now we need a photo to upload
        # read our test file
        cwd = os.getcwd()
        if 'tests' in cwd:
            path = '../photos/TestPic.JPG' #'../photos/Cute_Puppy.jpg'
        else:
            path = cwd + '/photos/TestPic.JPG' #'/photos/Cute_Puppy.jpg'
        ft = open(path, 'rb')
        ph = ft.read()
        ft.close()

        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        rsp = self.app.post(path='/photo', data=json.dumps(dict(category_id=c.id, extension=ext, image=b64img)),
                            headers=self.get_header_json())


    def test_event_category_list(self):

        tu1 = self.create_testuser_get_token()  # get a user so we can use the API
        tu2 = self.create_testuser_get_token()
        session = dbsetup.Session()
        event_details, open_cl = self.create_newevent_and_categories(session, tu1) # create an Event with categories (in PENDING state, also closes all other categories)
        category_list = event_details['categories']


        # all these categories are in the PENDING state
        # let's change them to upload and upload some photos to them
        for c in open_cl:
            c.state = category.CategoryState.UPLOAD.value
            session.add(c)
        session.commit()

        # we now have categories that will accept a photo
        for c in open_cl:
            for i in range(0, dbsetup.Configuration.UPLOAD_CATEGORY_PICS):
                self.set_token(tu1.get_token())
                self.upload_photo_to_category(c)
                self.set_token(tu2.get_token())
                self.upload_photo_to_category(c)

        session.close()

        # okay we should be able to request the category and get the categories we just created & populated
        rsp = self.app.get(path='/category', headers=self.get_header_html())
        assert(rsp.status_code == 200)
        categories = json.loads(rsp.data.decode('utf-8'))
        assert(len(categories) == len(open_cl))

class TestAdminAPIs(iiBaseUnitTest):

    def test_category_photolist_next(self):
        tu = self.create_testuser_get_token()

        session = dbsetup.Session()
        q = session.query(usermgr.User).filter(usermgr.User.emailaddress == tu.get_username())
        u = q.one()
        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(session, category.CategoryType.OPEN.value)
        session.commit()

        num_photos = 5
        for i in range (1,num_photos+1):
            p = photo.Photo()
            p.category_id = c.id
            p.filepath = 'boguspath'
            p.filename = str(uuid.uuid1()).translate({ord(c): None for c in '-'})
            p.user_id = u.id
            p.times_voted = 0
            p.score = i*4
            p.likes = 0
            p.active = 1
            session.add(p)

        session.commit()

        path = '/photo/{0}/next/0'.format(c.id)
        rsp = self.app.get(path=path, headers=self.get_header_html())
        c.state = category.CategoryState.CLOSED.value
        session.commit()

        session.rollback()
        session.close()
        assert (rsp.status_code == 200)


class TestUserLikes(iiBaseUnitTest):

    def test_user_likes_none(self):
        tu = self.create_testuser_get_token(make_staff=False)
        path = '/like/next/0'
        rsp = self.app.get(path=path, headers=self.get_header_html())
        assert(rsp.status_code == 204)
        assert( len(rsp.data) == 0)

    def test_user_likes_has_some(self):
        # Get a list of photos that user "likes".
        # Step #1 - create categories
        # Step #2 - create test users
        # Step #3 - create photos for test users for categories
        # Step #4 - create feedback (likes) for photos
        # Step #5 - have user request list of likes
        # Step #6 - validate list
        session = dbsetup.Session()
        me = self.create_testuser_get_token(make_staff=False)
        me._uid = self.get_user_id(session, me)
        pl, cl = self.create_test_categories_with_photos(session, num_categories=5, num_photos=25)
        assert(pl is not None)
        assert(len(pl) > 0)

        session.close()
        session = dbsetup.Session()

        # Now let's "like" all the odd photos
        for p in pl:
            if ( (p.id & 0x1) == 1):
                fm = categorymgr.FeedbackManager(uid=me._uid, pid=p.id, like=True)
                fm.create_feedback(session)

        session.commit()
        session.close()

        # now ask or the likes via the API
        self.set_token(me.get_token())
        rsp = self.app.get(path='/like/next/0', headers=self.get_header_html(), content_type='image/jpeg')
        assert(rsp.status_code == 200)

        user_likes = json.loads(rsp.data.decode('utf-8'))['likes']
        assert(user_likes is not None)

        for cphotos in user_likes:
            c = cphotos['category']
            photos = cphotos['photos']
            for photo in photos:
                assert( (photo['pid'] & 0x1) == 1)
                assert(photo['likes'] == 1)

        session.close()

class TestUserRewards(iiBaseUnitTest):

    def get_user_id(self,session, tu) -> int:

        au = usermgr.AnonUser.find_anon_user(session, tu.get_guid())
        assert(au is not None)
        return au.id

    def test_user_norewards(self):

        session = dbsetup.Session()
        me = self.create_testuser_get_token(make_staff=False)
        me._uid = self.get_user_id(session, me)

        self.set_token(me.get_token())
        rsp = self.app.get(path='/badges', headers=self.get_header_html(), content_type='image/jpeg')
        assert(rsp.status_code == 204)

class TestUpdatePhoto(iiBaseUnitTest):

    def test_update_photo_meta(self):

        session = dbsetup.Session()
        me = self.create_testuser_get_token(make_staff=False)
        me._uid = self.get_user_id(session, me)
        pl,cl = self.create_test_categories_with_photos(session, num_categories=1, num_photos=5)
        assert(pl is not None)
        assert(len(pl) > 0)
        session.close()
        session = dbsetup.Session()

        # now update the likes with a new user
        nu = self.create_testuser_get_token(make_staff=False)
        nu._uid = self.get_user_id(session, me)
        for p in pl:
            rsp = self.app.put(path='/update/photo/{0}'.format(p.id), headers=self.get_header_json(), data=json.dumps(dict({'like': True, 'flag': False, 'tags': ['tag1', 'tag2']})) )
            assert(rsp.status_code == 200)

        # now verify the likes
        cid = cl[0].id

        rsp = self.app.get(path='/like/next/0', headers=self.get_header_html())
        assert(rsp.status_code == 200)
        user_likes = json.loads(rsp.data.decode('utf-8'))['likes']
        for cphotos in user_likes:
            c = cphotos['category']
            photos = cphotos['photos']
            for photo in photos:
                assert(photo['likes'] == 1)
