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

class Test_oAuth2(DatabaseTest):

    def test_FAKESERVICEPROVIDER_always_works(self):
        self.setup()

        token = 'DUMMY TOKEN FOR FAKE SERVICE PROVIDER'
        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'FAKESERVICEPROVIDER')
        assert (u is not None)
        self.teardown()


    def test_is_oAuth2(self):
        assert(usermgr.UserAuth.is_oAuth2('Google', 'token') )
        assert(usermgr.UserAuth.is_oAuth2('Facebook', 'token') )
        assert(usermgr.UserAuth.is_oAuth2('GOOGLE', 'token') )
        assert(usermgr.UserAuth.is_oAuth2('FACEBOOK', 'token') )
        assert(not usermgr.UserAuth.is_oAuth2('Twitter', 'token') )
        assert(not usermgr.UserAuth.is_oAuth2('hcollins@hotmail.com', 'pa55w0rd') )

    def HIDE_test_authenticate(self):
        self.setup()
        token = 'ya29.GluFBB1Wn8JP9p4yEUM3FZ2ieCetp9yFCe1gcJbIPg6dJGXVvdn3QZCzXv1EKnUlelEYlVaH7rd9U1JKnfNrCyN5craemsExlnKEhYXy98WdIfebEA-wlpDlQBZ1'
        u = usermgr.authenticate('Google', token)
        assert(u is not None)
        self.teardown()

    def test_facebook_with_good_token(self):
        self.setup()

        token = 'EAAU953rqsQoBAAovb10RC4VO0lsAdkcXFsIkpaZAaDO1yAOpgvsG5Nq00qOXZBcTfIYbqhBbp7ZAZCHctO7ke2ZC6UN5myP2A3OOZAiRrXfLC91JRQ9JZB95XSrRra9oO1BE1CQhQbZA2iRVfKZBYsGJdykEgtwaMs0EZD'
        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Facebook')
        assert (u is not None)
        self.teardown()

    def HIDE_test_google_with_good_token(self):
        self.setup()

        token = 'ya29.GluFBB1Wn8JP9p4yEUM3FZ2ieCetp9yFCe1gcJbIPg6dJGXVvdn3QZCzXv1EKnUlelEYlVaH7rd9U1JKnfNrCyN5craemsExlnKEhYXy98WdIfebEA-wlpDlQBZ1'
        o = usermgr.UserAuth()

        u = o.authenticate_user(self.session, token, 'Google')
        assert(u is not None)
        self.teardown()

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
