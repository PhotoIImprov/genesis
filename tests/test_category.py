import initschema
import datetime

from models import resources
from models import usermgr

from models import category, voting, photo
from tests import DatabaseTest
import os
import json


class TestCategory(DatabaseTest):

    def create_category(self):
        # first we need a resource
        r = resources.Resource.create_resource(1111, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category & the image indexer
        s_date = datetime.datetime.now()
        e_date =  s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date, category.CategoryState.UPLOAD)
        category.Category.write_category(self.session, c)
        return c.id

    def test_current_category(self):
        self.setup()

        # we need a valid user id
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f00267A')

        dummy_uid = au.get_id()
        # see if we have a category already in the DB
        c = category.Category.current_category(self.session, dummy_uid, category.CategoryState.UPLOAD) # for now uid is dummy & not used
        if c is None:
            # if no category in the DB, create one and read it back
            cid = self.create_category()
            c = category.Category.current_category(self.session, dummy_uid, category.CategoryState.UPLOAD) # for now uid is dummy & not used

        assert(c is not None)

        self.teardown()
