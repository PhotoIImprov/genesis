import os
import unittest
import uuid
import hashlib
import iiServer
import json

class TestLogin(unittest.TestCase):

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

    def register(self):
        return

    def test_registration(self):
        u = str(uuid.uuid1())
        u = u.translate({ord(c): None for c in '-'})
        p = hashlib.sha224(u.encode('utf-8')).hexdigest()

        rsp = self.app.post('/register', data=json.dumps(dict(username=u, password=p, guid=u)), headers={'content-type':'application/json'})
        assert(rsp.status_code == 201)
        return

    def test_login(self):
        pass

