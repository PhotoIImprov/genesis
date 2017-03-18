import initschema
import datetime

from models import resources
from models import usermgr

from models import category, voting, photo
from . import DatabaseTest
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
        c = category.Category.create_category(r.resource_id, s_date, e_date)
        category.Category.write_category(self.session, c)
        return c.id

    def test_current_category(self):
        self.setup()

        # see if we have a category already in the DB
        c = category.Category.current_category(self.session, 1, category.CategoryState.UPLOAD) # for now uid is dummy & not used
        if c is None:
            # if no category in the DB, create one and read it back
            cid = self.create_category()
            c = category.Category.current_category(self.session, 1) # for now uid is dummy & not used

        assert(c is not None)

        self.teardown()
        pass