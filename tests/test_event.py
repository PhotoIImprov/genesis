
from unittest import TestCase
import initschema
import datetime
import os, errno
from models import category, usermgr, event
from tests import DatabaseTest
from sqlalchemy import func
import dbsetup
import iiServer
from flask import Flask
from test_REST_login import TestUser
import uuid
from controllers import categorymgr


class TestEvent(DatabaseTest):

    def create_anon_user(self, session) -> usermgr.AnonUser:
        # create a user
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(session, guid)
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
        cl = categorymgr.EventManager.join_event(self.session, accesskey, u)
        assert(cl is not None)
        assert(len(cl) == 3)

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
        cl = categorymgr.EventManager.join_event(self.session, accesskey, u)
        assert(cl is not None)
        assert(len(cl) == 3)
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
        cl = categorymgr.EventManager.join_event(self.session, accesskey, u)
        assert(cl is not None)
        assert(len(cl) == 3)
        self.session.commit()

        # join a second time!!
        cl = categorymgr.EventManager.join_event(self.session, accesskey, u)
        assert(cl is not None)
        assert(len(cl) == 3)
        self.session.commit()

        # there should be an EventUser record created by that last commit, and only one!
        eu = self.session.query(event.EventUser).filter(event.EventUser.user_id == u.id).one()
        assert(eu is not None)

        self.teardown()

    def test_event_list(self):
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

        self.teardown()
