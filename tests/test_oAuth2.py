from unittest import TestCase
import initschema
import datetime
import os, errno
import uuid
from models import resources
from models import category, photo, usermgr, voting, sql_logging
from tests import DatabaseTest
import dbsetup
import logsetup
import logging
from sqlalchemy.sql import func
from handlers import dbg_handler
from logsetup import logger
import json

class Test_oAuth2(DatabaseTest):

    def test_FAKESERVICEPROVIDER_always_works(self):
        self.setup()

        token = 'DUMMY TOKEN FOR FAKE SERVICE PROVIDER'
        content = bytes('{"id": 12345678, "email": "testuser-oauth@imageimprov.com"}', 'utf-8')

        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'FAKESERVICEPROVIDER', debug_json=content)
        assert (u is not None)
        self.teardown()


    def test_FAKESERVICEPROVIDER_create_account(self):
        self.setup()

        token = 'DUMMY TOKEN FOR FAKE SERVICE PROVIDER'
        guid = str(uuid.uuid1()).upper().translate({ord(c): None for c in '-'})
        emailaddress = 'testuser{0}@test.com'.format(guid)
        id = 123456
        d = {'id': id, 'email': emailaddress}
        json_d = json.dumps(d)

        content = bytes(json_d, 'utf-8')

        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'FAKESERVICEPROVIDER', debug_json=content)
        assert (u is not None)
        self.teardown()

    def test_is_oAuth2(self):
        assert(usermgr.UserAuth.is_oAuth2('Google', 'token') )
        assert(usermgr.UserAuth.is_oAuth2('Facebook', 'token') )
        assert(usermgr.UserAuth.is_oAuth2('GOOGLE', 'token') )
        assert(usermgr.UserAuth.is_oAuth2('FACEBOOK', 'token') )
        assert(not usermgr.UserAuth.is_oAuth2('Twitter', 'token') )
        assert(not usermgr.UserAuth.is_oAuth2('hcollins@hotmail.com', 'pa55w0rd') )

    # def HIDE_test_authenticate(self):
    #     self.setup()
    #     token = 'ya29.GluFBB1Wn8JP9p4yEUM3FZ2ieCetp9yFCe1gcJbIPg6dJGXVvdn3QZCzXv1EKnUlelEYlVaH7rd9U1JKnfNrCyN5craemsExlnKEhYXy98WdIfebEA-wlpDlQBZ1'
    #     u = usermgr.authenticate('Google', token)
    #     assert(u is not None)
    #     self.teardown()
    #
    # def HIDE_test_facebook_with_good_token(self):
    #     '''
    #     this requires a live internet connection since it
    #     actually hits Facebook!
    #     :return:
    #     '''
    #     self.setup()
    #
    #     token = 'EAAU953rqsQoBAAovb10RC4VO0lsAdkcXFsIkpaZAaDO1yAOpgvsG5Nq00qOXZBcTfIYbqhBbp7ZAZCHctO7ke2ZC6UN5myP2A3OOZAiRrXfLC91JRQ9JZB95XSrRra9oO1BE1CQhQbZA2iRVfKZBYsGJdykEgtwaMs0EZD'
    #     o = usermgr.UserAuth()
    #
    #     u = o.authenticate_user(self.session, token, 'Facebook')
    #     assert (u is not None)
    #     self.teardown()
    #
    # def HIDE_test_google_with_good_token(self):
    #     self.setup()
    #
    #     token = 'ya29.GluFBB1Wn8JP9p4yEUM3FZ2ieCetp9yFCe1gcJbIPg6dJGXVvdn3QZCzXv1EKnUlelEYlVaH7rd9U1JKnfNrCyN5craemsExlnKEhYXy98WdIfebEA-wlpDlQBZ1'
    #     o = usermgr.UserAuth()
    #
    #     u = o.authenticate_user(self.session, token, 'Google')
    #     assert(u is not None)
    #     self.teardown()
    #
    def test_google_with_expired_token(self):
        self.setup()

        token = 'ya29.GluEBL91ax_u108tuszVgSzG-sLxUVSHKBEjgW-Q1yW25oDm0KazS5bjVUBpVFt6GaAjQ4lUeY-Qmp2KVPgf2nTf4XKzsVecSFqLRWaEgQsLz3rMuLnGR-ftOXap'
        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Google')
        assert(u is None)
        self.teardown()

    def test_google_invalid_token(self):

        self.setup()
        token ='invalid token'
        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Google')
        assert(u is None)

        self.teardown()

    def test_google_inject_content(self):

        self.setup()
        token ='invalid token'
        content = bytes('{"id": 12345678, "emails": [{"type": "account", "value": "testuser1@imageimprov.com"}] }', 'utf-8')

        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Google', debug_json=content)
        assert(u is not None)

        self.teardown()

    def test_google_inject_content_missing_emails(self):

        self.setup()
        token ='invalid token'
        content = bytes('{"id": 12345678}', 'utf-8')

        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Google', debug_json=content)
        assert(u is None)

        self.teardown()

    def test_facebook_inject_content(self):

        self.setup()
        token ='invalid token'
        content = bytes('{"id": 12345678, "email": "testuser-oauth@imageimprov.com"}', 'utf-8')

        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Facebook', debug_json=content)
        assert(u is not None)

        self.teardown()

    def test_facebook_inject_content_missing_email(self):
        """tests that if no email is given oAuth will fail"""
        self.setup()
        token ='invalid token'
        content = bytes('{"id": 12345678}', 'utf-8')

        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Facebook', debug_json=content)
        assert(u is None)

        self.teardown()

    def test_facebook_inject_content_missing_id(self):

        self.setup()
        token ='invalid token'
        content = bytes('{"NOT_id": 12345678, "email": "testuser1@imageimprov.com"}', 'utf-8')

        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Facebook', debug_json=content)
        assert u is None

        self.teardown()

    def test_invalid_serviceprovider(self):
        self.setup()
        token ='invalid token'
        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'NotAService')
        assert(u is None)

        self.teardown()

    def test_serviceprovider_is_None(self):
        self.setup()
        token ='invalid token'
        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, None)
        assert(u is None)

        self.teardown()

    def test_empty_token(self):
        self.setup()
        token = None
        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'NotAService')
        assert(u is None)

        self.teardown()

    def test_oauth_instantiation(self):
        self.setup()

        o = usermgr.UserAuth(uid=1, serviceprovider='Google', serviceprovider_id=2, version=3, token='a token')

        assert(o.id == 1)
        assert(o.serviceprovider == 'GOOGLE')
        assert(o.sid == 2)
        assert(o.version == 3)
        assert(o.token == 'a token')

        self.teardown()