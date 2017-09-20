
from unittest import TestCase
import initschema
import datetime
import os, errno
from models import category, usermgr, event, voting, photo
from tests import DatabaseTest
from sqlalchemy import func
import dbsetup
import iiServer
from flask import Flask
from test_REST_login import TestUser
import uuid
from controllers import categorymgr


class TestEvent(DatabaseTest):

    def write_photo_to_category(self, session, c: category.Category, au:usermgr.AnonUser) -> photo.Photo:

        fo = photo.Photo()
        pi = photo.PhotoImage()
        pi._extension = 'JPEG'

        # read our test file
        cwd = os.getcwd()
        if 'tests' in cwd:
            path = '../photos/TestPic.JPG' #'../photos/Cute_Puppy.jpg'
        else:
            path = cwd + '/photos/TestPic.JPG' #'/photos/Cute_Puppy.jpg'
        ft = open(path, 'rb')
        pi._binary_image = ft.read()
        ft.close()

        fo.category_id = c.id
        d = fo.save_user_image(session, pi, au.id, c.id)
        assert(d['error'] is None)
        fn = fo.filename
        session.commit() # Photo & PhotoMeta should be written out

        return fo

    def create_open_categories(self, session, state: int, num_categories: int) -> list:
        cl = []
        for i in range(0, num_categories):
            start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            category_description = "TestingCategory{0}".format(i)
            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
            c = cm.create_category(session, category.CategoryType.OPEN.value)
            c.state = category.CategoryState.UPLOAD.value
            cl.append(c)

        session.commit()
        return cl

    def close_existing_categories(self, session):
        q = session.query(category.Category). \
            filter(category.Category.state != category.CategoryState.CLOSED.value). \
            update({category.Category.state: category.CategoryState.CLOSED.value})
        session.commit()

    def create_anon_user(self, session, make_staff=False) -> usermgr.AnonUser:
        # create a user
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(session, guid)
        if make_staff:
            au.usertype = usermgr.UserType.IISTAFF.value

        session.commit() # write it out to get the id
        assert (au is not None)
        return au

    def create_user(self, session) -> usermgr.User:
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        bogusemail = guid + '@hotmail.com'
        u = usermgr.User.create_user(session, guid, bogusemail, 'pa55w0rd')
        session.commit()
        return u

    def test_event_init(self):
        self.setup()
        au = self.create_anon_user(self.session)
        e = event.Event(name='Test', max_players=10, user=au, active=False, accesskey='weird-foods')
        assert(e.user_id == au.id and e.name == 'Test' and not e.active and e.accesskey == 'weird-foods' and e.num_players == 10)
        self.teardown()

    def test_event_manager(self):
        self.setup()
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        u = self.create_user(self.session)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round', 'team'],
                               name='Test', max_players=10, user=u, active=False, accesskey='weird-foods')
        self.teardown()

    def test_create_event(self):
        self.setup()
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        u = self.create_user(self.session)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round', 'team'],
                               name='Test', max_players=10, user=u, active=False, accesskey='weird-foods')
        em.create_event(self.session)

        assert(len(em._cl) == 3)
        self.teardown()

    def test_event_manager_bad_date_too_early(self):
        self.setup()
        start_date = (datetime.datetime.now() - datetime.timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M')
        try:
            u = self.create_user(self.session)
            em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date,
                                    categories=['fluffy', 'round', 'team'],
                                    name='Test', max_players=10, user=u, active=False, accesskey='weird-foods')
            assert(False)
        except Exception as e:
            assert (e.args[1] == 'badargs')
        finally:
            self.teardown()

    def test_event_manager_bad_no_categories(self):
        self.setup()
        start_date = (datetime.datetime.now() - datetime.timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M')
        try:
            u = self.create_user(self.session)
            em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date,
                                    categories=None,
                                    name='Test', max_players=10, user=u, active=False, accesskey='weird-foods')
            assert(False)
        except Exception as e:
            assert (e.args[1] == 'badargs')
        finally:
            self.teardown()

    def test_pass_phrase(self):
        self.setup()

        try:
            passphrase = categorymgr.PassPhraseManager().select_passphrase(self.session)
            assert(passphrase is not None)
            assert(len(passphrase) == 9)
        except Exception as e:
            assert(False)
        finally:
            self.teardown()

    def test_join_event_creator(self):
        self.setup()
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        u = self.create_user(self.session)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round', 'team'],
                               name='Test', max_players=10, user=u, active=False, accesskey='weird-foods')
        em.create_event(self.session)

        accesskey = em._e.accesskey
        assert(accesskey is not None)

        # let's try to join this event, we are already in it so no harm, no foul
        e = categorymgr.EventManager.join_event(self.session, accesskey, u)
        assert(e is not None)
        assert(e._cl is not None)
        assert(len(e._cl) == 3)

        self.teardown()

    def test_join_event_user(self):
        self.setup()
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        u = self.create_user(self.session)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round', 'team'],
                               name='Test', max_players=10, user=u, active=False, accesskey='weird-foods')
        em.create_event(self.session)

        accesskey = em._e.accesskey
        assert(accesskey is not None)

        # let's try to join this event, we are already in it so no harm, no foul
        u = self.create_user(self.session)
        e = categorymgr.EventManager.join_event(self.session, accesskey, u)
        assert(e is not None)
        assert(e._cl is not None)
        assert(len(e._cl) == 3)
        self.session.commit()

        # there should be an EventUser record created by that last commit, and only one!
        eu = self.session.query(event.EventUser).filter(event.EventUser.user_id == u.id).one()
        assert(eu is not None)

        self.teardown()

    def test_join_event_twice(self):
        self.setup()
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        u = self.create_user(self.session)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round', 'team'],
                               name='Test', max_players=10, user=u, active=False)
        em.create_event(self.session)

        accesskey = em._e.accesskey
        assert(accesskey is not None)

        # let's try to join this event, we are already in it so no harm, no foul
        u = self.create_user(self.session)
        e = categorymgr.EventManager.join_event(self.session, accesskey, u)
        assert(e is not None)
        assert(e._cl is not None)
        assert(len(e._cl) == 3)
        self.session.commit()

        # join a second time!!
        e = categorymgr.EventManager.join_event(self.session, accesskey, u)
        assert(e is not None)
        assert(e._cl is not None)
        assert(len(e._cl) == 3)
        self.session.commit()

        # there should be an EventUser record created by that last commit, and only one!
        eu = self.session.query(event.EventUser).filter(event.EventUser.user_id == u.id).one()
        assert(eu is not None)

        self.teardown()

    def test_event_list_me(self):
        self.setup()
        # first create an event
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        au = self.create_anon_user(self.session)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round'],
                               name='EventList Test#1', max_players=10, user=au, active=False)
        e1 = em.create_event(self.session)

        assert(len(em._cl) == 2)

        # let's create a second event
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        em = categorymgr.EventManager(vote_duration=36, upload_duration=96, start_date=start_date, categories=['square', 'beer', 'dogs'],
                               name='EventList Test#2', max_players=8, user=au, active=False)
        e2 = em.create_event(self.session)
        assert(len(em._cl) == 3)

        # now see if we can read this event list for the user
        d_el = em.events_for_user(self.session, au)
        assert(len(d_el) == 2)

        # check the data thoroughly
        for e in d_el:
            if e['name'] == 'EventList Test #1':
                assert(e['max_players'] == 10)
                assert(len(e['categories']) == 2)
                assert(e['id'] == e1.id)
            if e['name'] == 'EventList Test #2':
                assert(e['max_players'] == 8)
                assert(len(e['categories']) == 3)
                assert(e['id'] == e2.id)
            assert(e['created_by'] == 'me')

        self.teardown()

    def test_event_list_unknown(self):
        self.setup()
        # first create an event
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        au = self.create_anon_user(self.session)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round'],
                               name='EventList Test#1', max_players=10, user=au, active=False)
        event_created = em.create_event(self.session)

        assert(len(em._cl) == 2)

        # create new, anon user and create and add them to the event
        au = self.create_anon_user(self.session)
        event_joined = em.join_event(self.session, event_created.accesskey, au)
        assert(event_joined.id == event_created.id)

        # now see if we can read this event list for the user
        d_el = em.events_for_user(self.session, au)
        assert(len(d_el) == 1)

        # check the data thoroughly
        for e in d_el:
            assert(e['created_by'] == '??')

        self.teardown()

    def test_event_list_iistaff(self):
        self.setup()
        # first create an event
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        au = self.create_anon_user(self.session, make_staff=True)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round'],
                               name='EventList Test#1', max_players=10, user=au, active=False)
        event_created = em.create_event(self.session)

        assert(len(em._cl) == 2)

        # create new, anon user and create and add them to the event
        au = self.create_anon_user(self.session)
        event_joined = em.join_event(self.session, event_created.accesskey, au)
        assert(event_joined.id == event_created.id)

        # now see if we can read this event list for the user
        d_el = em.events_for_user(self.session, au)
        assert(len(d_el) == 1)

        # check the data thoroughly
        for e in d_el:
            assert(e['created_by'] == 'Image Improv')

        self.teardown()

    def test_event_list_player(self):
        self.setup()
        # first create an event
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        u = self.create_user(self.session)
        au = usermgr.AnonUser.get_anon_user_by_id(self.session, u.id)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round'],
                               name='EventList Test#1', max_players=10, user=au, active=False)
        event_created = em.create_event(self.session)

        assert(len(em._cl) == 2)

        # create new, anon user and create and add them to the event
        au = self.create_anon_user(self.session)
        event_joined = em.join_event(self.session, event_created.accesskey, au)
        assert(event_joined.id == event_created.id)

        # now see if we can read this event list for the user
        d_el = em.events_for_user(self.session, au)
        assert(len(d_el) == 1)

        # check the data thoroughly
        for e in d_el:
            assert(e['created_by'] == u.emailaddress)

        self.teardown()

    def active_voting_list_for_events_by_state(self, state_for_list: int):

        # setup some OPEN categories
        self.close_existing_categories(self.session)
        num_categories = 5
        cl = self.create_open_categories(self.session, state=category.CategoryState.UPLOAD.value, num_categories=num_categories)
        assert(len(cl) == num_categories)
        au = self.create_anon_user(self.session)
        second_au = self.create_anon_user(self.session)
        assert(au is not None)
        assert(second_au is not None)

        # put Photos in our new categories so they'll show up in lists
        # write some photos out to these categories
        for c in cl:
            for i in range(0, dbsetup.Configuration.UPLOAD_CATEGORY_PICS):
                self.write_photo_to_category(self.session, c, au)
                self.write_photo_to_category(self.session, c, second_au)

        active_open_cl = categorymgr.BallotManager().active_voting_categories(self.session, au.id)

        # now create an event with Categories
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round'],
                               name='EventList Test#1', max_players=10, user=au, active=False)
        e1 = em.create_event(self.session)
        assert(len(em._cl) == 2)

        # change the category state to reflect what state we are testing
        for c in em._cl:
            c.state = category.CategoryState.UPLOAD.value
        self.session.commit()

        # now upload photos to these categories
        for c in em._cl:
            for i in range(0, dbsetup.Configuration.UPLOAD_CATEGORY_PICS):
                self.write_photo_to_category(self.session, c, au)
                self.write_photo_to_category(self.session, c, second_au)

        # change the category state to reflect what state we are testing
        for c in em._cl:
            c.state = state_for_list
        for c in cl:
            c.state= state_for_list

        self.session.commit()

        active_cl = categorymgr.BallotManager().active_voting_categories(self.session, au.id)
        assert(len(active_cl) == (len(em._cl) + len(cl)))
        self.teardown()

    def test_active_voting_list_for_events_upload_state(self):
        self.setup()
        self.active_voting_list_for_events_by_state(category.CategoryState.UPLOAD.value)
        self.teardown()

    def test_active_voting_list_for_events_voting_state(self):
        self.setup()
        self. active_voting_list_for_events_by_state(category.CategoryState.VOTING.value)
        self.teardown()

    # def test_active_voting_list_for_voting_state(self):
    #     self.setup()
    #
    #     self.close_existing_categories(self.session)
    #     num_categories = 5
    #     cl = self.create_open_categories(self.session, state=category.CategoryState.UPLOAD.value, num_categories=num_categories)
    #     assert(len(cl) == num_categories)
    #     au = self.create_anon_user(self.session)
    #     second_au = self.create_anon_user(self.session)
    #     assert(au is not None)
    #     bm = voting.BallotManager()
    #     active_cl = bm.active_voting_categories(self.session, au.id)
    #
    #     # we have no photos for these categories, so
    #     assert(len(active_cl) == 0)
    #
    #     # write some photos out to these categories
    #     for c in cl:
    #         for i in range(0, dbsetup.Configuration.UPLOAD_CATEGORY_PICS):
    #             self.write_photo_to_category(self.session, c, au)
    #             self.write_photo_to_category(self.session, c, second_au)
    #
    #     for c in cl:
    #         c.state = category.CategoryState.VOTING.value
    #     self.session.commit()
    #
    #     # since au uploaded, once there are 4 photos not uploaded by au we can
    #     # "see" the category list
    #     active_cl = bm.active_voting_categories(self.session, au.id)
    #
    #     # we have no photos for these categories, so
    #     assert (len(active_cl) == len(cl))
    #
    #     # okay, so active returns the # categories we just created. Now create an event
    #     # and see if it's categories are added.
    #     self.teardown()
    #
    # def test_active_voting_list_for_upload_state(self):
    #     self.setup()
    #
    #     self.close_existing_categories(self.session)
    #     num_categories = 5
    #     cl = self.create_open_categories(self.session, state=category.CategoryState.UPLOAD.value, num_categories=num_categories)
    #     assert(len(cl) == num_categories)
    #     au = self.create_anon_user(self.session)
    #     second_au = self.create_anon_user(self.session)
    #     assert(au is not None)
    #     bm = voting.BallotManager()
    #     active_cl = bm.active_voting_categories(self.session, au.id)
    #
    #     # we have no photos for these categories, so
    #     assert(len(active_cl) == 0)
    #
    #     # write some photos out to these categories
    #     for c in cl:
    #         for i in range(0, dbsetup.Configuration.UPLOAD_CATEGORY_PICS):
    #             self.write_photo_to_category(self.session, c, au)
    #             self.write_photo_to_category(self.session, c, second_au)
    #
    #     # since au uploaded, once there are 4 photos not uploaded by au we can
    #     # "see" the category list
    #     active_cl = bm.active_voting_categories(self.session, au.id)
    #
    #     # we have no photos for these categories, so
    #     assert (len(active_cl) == len(cl))
    #
    #     # okay, so active returns the # categories we just created. Now create an event
    #     # and see if it's categories are added.
    #     self.teardown()

    def test_event_detail(self):
        self.setup()

        # first create an event
        start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        au = self.create_anon_user(self.session)
        em = categorymgr.EventManager(vote_duration=24, upload_duration=72, start_date=start_date, categories=['fluffy', 'round'],
                               name='EventList Test#1', max_players=10, user=au, active=False)
        e = em.create_event(self.session)

        assert(len(em._cl) == 2)

        # now get the details for the first element
        e_dict = categorymgr.EventManager.event_details(self.session, au, e.id)
        assert(e_dict is not None)
        cl = e_dict['categories']
        assert(len(cl) == 2)
        for c in cl:
            assert(c['num_players'] == 0 and c['num_photos'] == 0)

        self.teardown()