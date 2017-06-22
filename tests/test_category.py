import initschema
import datetime

from models import resources
from models import usermgr

from models import category, voting, photo
from tests import DatabaseTest
import os
import json
import errno
import logsetup
import logging
from handlers import dbg_handler
from logsetup import logger


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

    def test_is_upload(self):
        c = category.Category()
        c.state = category.CategoryState.UPLOAD.value
        assert(c.is_upload())

        c.state = category.CategoryState.VOTING.value
        assert(not c.is_upload())

    def test_is_voting(self):
        c = category.Category()
        c.state = category.CategoryState.VOTING.value
        assert(c.is_voting())

        c.state = category.CategoryState.VOTING.value
        assert(not c.is_upload())

    def test_to_json_exception(self):

        c = category.Category()
        hndlr = dbg_handler.DebugHandler()
        logger.addHandler(hndlr)
        hndlr._dbg_log = None
        logsetup.logger.setLevel(logging.INFO)
        logsetup.hndlr.setLevel(logging.INFO)
        try:
            c.to_json()
            assert (False)
        except Exception as e:
            log = hndlr._dbg_log
            assert(log is not None)
            assert(log['msg'] == 'error json category values')

    def test_category_states(self):

        str = category.CategoryState.to_str(category.CategoryState.UNKNOWN.value)
        assert(str == 'UNKNOWN')

        str = category.CategoryState.to_str(category.CategoryState.CLOSED.value)
        assert(str == 'CLOSED')

        str = category.CategoryState.to_str(category.CategoryState.COUNTING.value)
        assert(str == 'COUNTING')

        str = category.CategoryState.to_str(5555)
        assert(str == 'INVALID')
