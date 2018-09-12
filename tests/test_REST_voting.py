"""
test_REST_voting.py
===================
We will test the voting API via the REST interface. We need to do the following:

    1) Register test users
        a) both anonymous and email accounts
    2) Upload photos to a category
    3) Switch category to voting state (round 1)
    4) Vote
    5) Switch category to voting state (round 2)
    6) Vote
    7) Close out category, see results

"""
import unittest
import uuid
import hashlib
import iiServer
import json
import base64
import datetime
import dbsetup
from models import category, resources
from collections import namedtuple
import requests
from models import error
from urllib.parse import urlencode
from werkzeug.datastructures import Headers
from random import shuffle
from tests.utilities import get_photo_fullpath

class TestUser:
    _u = None   # username
    _p = None   # password
    _g = None   # guid
    _uid = None  # user_id
    _cid = None #category id
    _token = None # JWT token

    def __init__(self):
        self.app = iiServer.app.test_client()

    def create_anon_user(self):
        self._u = str(uuid.uuid1())
        self._u = self._u.translate({ord(c): None for c in '-'})
        self._p = hashlib.sha224(self._u.encode('utf-8')).hexdigest()
        self._g = self._u

    def create_user_with_name(self, username):
        self._p = 'pa55w0rd'
        self._g = str(uuid.uuid1())
        self._g = self._g.translate({ord(c): None for c in '-'})

        # real users have emails as their username
        self._u = username

    def register_user(self):
        rsp = self.app.post(path='/register', data=json.dumps(dict(username=self._u, password=self._p, guid=self._g)),
                            headers={'content-type': 'application/json'})
        assert (rsp.status_code == 201 or rsp.status_code == 400)
        return rsp

    def authorize_user(self):
        rsp = self.app.post(path='/auth', data=json.dumps(dict(username=self._u, password=self._p)),
                            headers={'content-type': 'application/json'})
        assert (rsp.status_code == 200)
        assert (rsp.content_type == 'application/json')
        data = json.loads(rsp.data.decode("utf-8"))
        self._token = data['access_token']
        return rsp

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

class TestVotingRounds(unittest.TestCase):

    _NUM_ANON_USERS = 5           # number of anonymous users to simulate
    _NUM_KNOWN_USERS = 10          # number of named users to simulate
    _NUM_TIMES_TO_VOTE_ROUND1 = 5   # number of times to vote in round 1
    _NUM_TIMES_TO_VOTE_ROUND2 = 5   # number of times to voite in round 2
    _NUM_SECTIONS_ROUND2 = 4        # the "stratification" of voting in round 2

    _users = []     # list of all users
    _tu = None      # this is our test user to access interface

    def setUp(self):
        self.app = iiServer.app.test_client()

    def create_tst_users(self):
        # okay we'll create anonymous and known test users
        for i in range(self._NUM_ANON_USERS):
            tu = TestUser()
            tu.create_anon_user()
            tu.register_user()
            tu.authorize_user()
            self._users.append(tu)

        for i in range(self._NUM_KNOWN_USERS):
            tu = TestUser()
            uname = 'testuser{}@gmail.com'.format(i)
            tu.create_user_with_name(uname)
            tu.register_user()
            tu.authorize_user()
            self._users.append(tu)

        shuffle(self._users)

    def json_header(self, token):
        assert (token is not None)
        headers = Headers()
        headers.add('content-type', 'application/json')
        headers.add('Authorization', 'JWT ' + token)
        return headers

    def html_header(self, token):
        assert(token is not None)
        headers = Headers()
        headers.add('content-type', 'text/html')
        headers.add('Authorization', 'JWT ' + token)
        return headers

    def upload_photo(self, tu, cid, photo_name):
        ft = open(get_photo_fullpath(photo_name), 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        # okay, we need to post this
        ext = 'JPEG'
        img = base64.standard_b64encode(ph)
        b64img = img.decode("utf-8")
        rsp = self.app.post(path='/photo', data=json.dumps(dict(category_id=cid, extension=ext, image=b64img)), headers=self.json_header(tu._token))
        assert (rsp.status_code == 201)
        return rsp

    def get_ballot(self, tu, cid):
        rsp = self.app.get(path='/ballot', query_string=urlencode({'category_id':cid}), headers=self.html_header(tu._token))
        data = json.loads(rsp.data.decode("utf-8"))
        assert(rsp.status_code == 200)
        ballots = data
        assert(len(ballots) == 4)
        return ballots

    def vote_ballot(self, tu, ballots):
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
        rsp = self.app.post(path='/vote', data=jvotes, headers=self.json_header(tu._token))
        assert(rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        ballots = data
        assert(len(ballots) == 4)
        return ballots

    def read_category(self, token):
        rsp =  self.app.get(path='/category',headers=self.html_header(token))
        assert(rsp.status_code == 200)
        data = json.loads(rsp.data.decode("utf-8"))
        return data

    def get_category_by_state(self, target_state, token):

        cl = self.read_category(token)
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
                            headers=self.json_header(token))
        assert(rsp.status_code == 200)
        return cid

    def upload_category(self,token):
        cid = self.get_category_by_state(category.CategoryState.UPLOAD, token)
        return cid

    def set_category_to_voting(self, token, cid):
        # set category to voting
        rsp = self.app.post(path='/setcategorystate', data=json.dumps(dict(category_id=cid, state=category.CategoryState.VOTING.value)),
                            headers=self.json_header(token))
        assert(rsp.status_code == 200)
        return rsp

    def setup_round2(self, cid):
        # need to execute stored proc in DB to switch to round 2
#        results = dbsetup.engine.execute('sp_initialize_round2 :p1, :p2', {'p1':self._NUM_SECTIONS_ROUND2, 'p2': cid})
        connection = dbsetup.engine.raw_connection()
        cursor = connection.cursor()
        results = cursor.callproc("sp_initialize_round2", [self._NUM_SECTIONS_ROUND2, cid])
        cursor.close()
        connection.commit()
        return results

    def MAIN_setup_users(self):
        self.setUp()
        self.create_tst_users()
        self._tu = TestUser()
        self._tu.create_anon_user()
        self._tu.register_user()
        self._tu.authorize_user()
        token = self._tu._token
        cid = self.upload_category(token) # find upload category or make one!

#        self.setup_round2(cid)

        for p in _photos:
            for tu in self._users:
                self.upload_photo(tu, cid, p)

        # we've done our uploads, time to switch to voting...
        self.set_category_to_voting(token, cid)

        # now we can vote
        for tu in self._users:
            ballots = self.get_ballot(tu, cid)
            for i in range(self._NUM_TIMES_TO_VOTE_ROUND1):
                ballots = self.vote_ballot(tu, ballots)

        # now switch to round #2
        self.setup_round2(cid)

        # now let's vote
        for tu in self._users:
            ballots = self.get_ballot(tu, cid)
            for i in range(self._NUM_TIMES_TO_VOTE_ROUND2):
                ballots = self.vote_ballot(tu, ballots)
