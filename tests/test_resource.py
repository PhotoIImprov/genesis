import initschema
import datetime

from models import resources
from models import usermgr

from models import category, voting, photo
from . import DatabaseTest
import os
import json

class TestResource(DatabaseTest):

    def test_load_resources(self):
        self.setup()

        rlist = resources.Resource.load_resources(self.session)
        assert(rlist is None)

    def test_create_resource(self):
        self.setup()

        r = resources.Resource.create_resource(1111, 'EN', 'Kittens')
        assert(r is not None)

        resources.Resource.write_resource(self.session, r)

        self.teardown()
