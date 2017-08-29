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


class TestEvent(DatabaseTest):

    def test_event_init(self):
        e = event.Event(name='Test', max_players=10, user_id=5, active=False, accesskey='weird-foods')
        assert(e.user_id == 5 and e.name == 'Test' and not e.active and e.accesskey == 'weird-foods' and e.max_players == 10)
