
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

    def create_user(self, session):
        guid = str(uuid.uuid1())
        guid = guid.upper().translate({ord(c): None for c in '-'})
        bogusemail = guid + '@hotmail.com'
        u = usermgr.User.create_user(session, guid, bogusemail, 'pa55w0rd')
        session.commit()
        return u

    def test_event_init(self):
        self.setup()
        u = self.create_user(self.session)
        e = event.Event(name='Test', max_players=10, user=u, active=False, accesskey='weird-foods')
        assert(e.user_id == u.id and e.name == 'Test' and not e.active and e.accesskey == 'weird-foods' and e.max_players == 10)
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
