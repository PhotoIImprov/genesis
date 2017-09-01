import initschema
import datetime

from models import resources
from models import usermgr

from models import category, voting, photo
from controllers import categorymgr

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
from models import event

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

        u = usermgr.User()
        cl = category.Category.active_categories(self.session, u)
        assert(cl is None)

    def test_all_category_bad_user(self):
        self.setup()

        u = usermgr.User()
        cl = category.Category.all_categories(self.session, u)
        assert(cl is None)

    def test_active_category_no_args(self):
        session = 1
        cl = category.Category.active_categories(session, None)
        assert(cl is None)

        try:
            au = usermgr.AnonUser()
            cl = category.Category.active_categories(None, au)
            assert(False)
        except Exception as e:
            assert(e.args[0] == "'NoneType' object has no attribute 'query'")

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
        au = self.session.query(usermgr.AnonUser).get(max_uid)
        return au

    def test_category_tag_list(self):
        self.setup()
        au = self.get_active_user()
        clist = category.Category.active_categories(self.session, au)
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

        au = self.get_active_user()
        clist = category.Category.all_categories(self.session, au)
        assert(len(clist) != 0)
        assert(len(clist) <= category._CATEGORYLIST_MAXSIZE)

        self.teardown()

    def test_category_manager(self):
        self.setup()

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(self.session, category.CategoryType.OPEN.value)
        self.session.commit()
        assert(c is not None)

        self.teardown()

    def test_category_manager_reuse_resource(self):
        self.setup()

        guid = str(uuid.uuid1())
        category_description = guid.upper().translate({ord(c): None for c in '-'})
        start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c = cm.create_category(self.session, category.CategoryType.OPEN.value)
        self.session.commit()
        assert(c is not None)

        cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
        c1 = cm.create_category(self.session, category.CategoryType.OPEN.value)
        self.session.commit()
        assert(c1 is not None)

        assert(c.resource_id == c1.resource_id)
        self.teardown()

    def test_category_manager_upload_negative(self):

        try:
            start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=-5, vote_duration=72, description='test_category_manager_upload_negative')
            assert(False)
        except Exception as e:
            assert(e.args[1] == 'badargs')

    def test_category_manager_vote_negative(self):

        try:
            start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=20, vote_duration=-72,
                                          description='test_category_manager_vote_negative')
            assert (False)
        except Exception as e:
            assert (e.args[1] == 'badargs')

    def test_category_manager_vote_too_large(self):

        try:
            start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=20, vote_duration=24*15,
                                          description='test_category_manager_vote_too_large')
            assert (False)
        except Exception as e:
            assert (e.args[1] == 'badargs')

    def test_category_manager_upload_too_large(self):

        try:
            start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24*15, vote_duration=24,
                                          description='test_category_manager_upload_too_large')
            assert (False)
        except Exception as e:
            assert (e.args[1] == 'badargs')

    def test_category_manager_upload_not_int(self):

        try:
            start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration='72', vote_duration=24,
                                          description='test_category_manager_upload_not_int')
            assert (False)
        except Exception as e:
            assert (e.args[1] == 'badargs')

    def test_category_manager_vote_not_int(self):

        try:
            start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=72, vote_duration='24',
                                          description='test_category_manager_vote_not_int')
            assert (False)
        except Exception as e:
            assert (e.args[1] == 'badargs')

    def test_category_manager_start_too_early(self):

        try:
            start_date = (datetime.datetime.now() - datetime.timedelta(minutes=10) ).strftime('%Y-%m-%d %H:%M')
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=72, vote_duration=24,
                                          description='test_category_manager_start_too_early')
            assert (False)
        except Exception as e:
            assert (e.args[1] == 'badargs')

    def create_anon_user(self, session):
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(session, guid)
        session.commit()
        return au

    def test_event_categories(self):
        self.setup()
        # first we need a user
        au = self.create_anon_user(self.session)
        uid = au.id
        self.session.add(au)  # in case it needs it's attributes refreshed ???

        try:
            start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date,
                                    categories=['fluffy', 'round', 'team'],
                                    name='Test', max_players=10, user=au, active=False, accesskey='weird-foods')
            e = em.create_event(self.session)
            assert (len(em._cl) == 3)
            assert(e is not None)

            eu = self.session.query(event.EventUser).filter(event.EventUser.user_id == uid).all()
            assert(eu is not None)

            # okay we now have 3 legit categories tied to this user
            # put them in the UPLOAD state
            for c in em._cl:
                c.state = category.CategoryState.UPLOAD.value
            self.session.commit()

            cm = categorymgr.CategoryManager()
            cl = cm.active_categories_for_user(self.session, au)
            assert(cl is not None)
            assert(len(cl) >= len(em._cl))

            # try another user that shouldn't get the new categories
            au = self.create_anon_user(self.session)
            uid = au.id
            self.session.add(au)  # in case it needs it's attributes refreshed ???
            cl_short = cm.active_categories_for_user(self.session, au)
            assert(len(cl) > len(cl_short))

        except Exception as e:
            assert(False)
        finally:
            self.session.close()
            self.teardown()