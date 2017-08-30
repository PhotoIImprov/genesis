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
from sqlalchemy import func
import uuid


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

    def test_all_category_bad_user(self):
        self.setup()

        cl = category.Category.all_categories(self.session, 0)
        assert(cl is None)

    def test_active_category_no_args(self):
        session = 1
        cl = category.Category.active_categories(session, None)
        assert(cl is None)

        cl = category.Category.active_categories(None, 3)
        assert(cl is None)

    def test_all_category_no_args(self):
        session = 1
        cl = category.Category.all_categories(session, None)
        assert(cl is None)

        cl = category.Category.all_categories(None, 3)
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
        assert(str == 'PENDING')

        str = category.CategoryState.to_str(category.CategoryState.CLOSED.value)
        assert(str == 'CLOSED')

        str = category.CategoryState.to_str(category.CategoryState.COUNTING.value)
        assert(str == 'COUNTING')

        str = category.CategoryState.to_str(5555)
        assert(str == 'INVALID')

    def test_empty_category_tag_list(self):
        self.setup()
        ctags = category.CategoryTagList()
        tag_list = ctags.read_category_tags(0, self.session)
        assert(len(tag_list) == 0)
        self.teardown()

    def get_active_user(self):
        max_uid = self.session.query(func.max(usermgr.AnonUser.id)).one()
        return max_uid

    def test_category_tag_list(self):
        self.setup()
        uid = self.get_active_user()
        clist = category.Category.active_categories(self.session, uid[0])
        assert(len(clist) != 0)

        ctags = category.CategoryTagList()
        for c in clist:
            tag_list = ctags.read_category_tags(c.id, self.session)
            if (len(tag_list) == 0):
                # we found a category with no tags, let's create some
                max_resource_id = self.session.query(func.max(resources.Resource.resource_id)).one()
                rid = max_resource_id[0]
                for i in range(1,5):
                    r = resources.Resource.create_resource(rid+i, 'EN', 'tag{0}'.format(i))
                    resources.Resource.write_resource(self.session, r)
                    ctag = category.CategoryTag(category_id=c.id, resource_id = rid+i)
                    self.session.add(ctag)
                self.session.commit()
                break

        new_tag_list = ctags.read_category_tags(c.id, self.session)
        assert(len(new_tag_list) == 4)

        self.teardown()

    def test_read_all_categories(self):
        self.setup()

        uid = self.get_active_user()
        clist = category.Category.all_categories(self.session, uid[0])
        assert(len(clist) != 0)
        assert(len(clist) <= category._CATEGORYLIST_MAXSIZE)

        self.teardown()

    def test_category_manager(self):
        self.setup()

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})

        cm = category.CategoryManager(start_date='2017-09-01 11:00', upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(self.session, category.CategoryType.OPEN.value)
        self.session.commit()
        assert(c is not None)

        self.teardown()

    def test_category_manager_reuse_resource(self):
        self.setup()

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})

        cm = category.CategoryManager(start_date='2017-09-01 11:00', upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(self.session, category.CategoryType.OPEN.value)
        self.session.commit()
        assert(c is not None)

        cm = category.CategoryManager(start_date='2017-09-03 11:00', upload_duration=24, vote_duration=72, description=category_description)
        c1 = cm.create_category(self.session, category.CategoryType.OPEN.value)
        self.session.commit()
        assert(c1 is not None)

        assert(c.resource_id == c1.resource_id)
        self.teardown()
