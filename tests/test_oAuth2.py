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
