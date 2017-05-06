import initschema
import datetime

from models import resources
from models import usermgr

from models import category, voting, photo
from tests import DatabaseTest
import os
import json
import errno


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

    def test_active_category_bad_user(self):
        self.setup()

        cl = category.Category.active_categories(self.session, 0)
        assert(cl is None)

    def test_active_category_no_args(self):
        session = 1
        cl = category.Category.active_categories(session, None)
        assert(cl is None)

        cl = category.Category.active_categories(None, 3)
        assert(cl is None)

    def test_read_category_by_id_no_args(self):
        try:
            c = category.Category.read_category_by_id(None, None)
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)
            pass

    def test_is_upload(self):
        c = category.Category()
        c.state = category.CategoryState.UPLOAD.value
        assert(c.is_upload())

        c.state = category.CategoryState.VOTING.value
        assert(not c.is_upload())

    def test_category_states(self):

        str = category.CategoryState.to_str(category.CategoryState.UNKNOWN.value)
        assert(str == 'UNKNOWN')

        str = category.CategoryState.to_str(category.CategoryState.CLOSED.value)
        assert(str == 'CLOSED')

        str = category.CategoryState.to_str(category.CategoryState.COUNTING.value)
        assert(str == 'COUNTING')

        str = category.CategoryState.to_str(5555)
        assert(str == 'INVALID')
