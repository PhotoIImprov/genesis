from unittest import TestCase
import dbsetup
from dbsetup import EnvironmentType

class TestDBsetup(TestCase):
    def test_connection_string(self):
        cs = dbsetup.connection_string(EnvironmentType.DEV)
        assert(cs == "mysql+pymysql://python:python@192.168.1.149:3306/imageimprov")
        cs = dbsetup.connection_string(EnvironmentType.PROD)
        assert(cs == "mysql+pymysql://python:python@104.196.212.140:3306/imageimprov")

    def test_environment(self):
        env = dbsetup.determine_environment("PROD")
        assert(env == EnvironmentType.PROD)

        env = dbsetup.determine_environment("INSTANCE")
        assert(env == EnvironmentType.PROD)

        env = dbsetup.determine_environment("DEV")
        assert(env == EnvironmentType.DEV)

        env = dbsetup.determine_environment("STAGE")
        assert(env == EnvironmentType.STAGE)

        env = dbsetup.determine_environment("QA")
        assert(env == EnvironmentType.QA)