from unittest import TestCase
import dbsetup
from dbsetup import EnvironmentType

class TestDBsetup(TestCase):
    def test_connection_string(self):
        cs = dbsetup.connection_string(EnvironmentType.DEV)
        assert(cs == "mysql+pymysql://python:python@192.168.1.149:3306/imageimprov")
        cs = dbsetup.connection_string(EnvironmentType.PROD)
        assert(cs == "mysql+pymysql://python:python@127.0.0.1:3306/imageimprov")
        cs = dbsetup.connection_string(EnvironmentType.UNKNOWN)
        assert(cs is None)

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

        env = dbsetup.determine_environment("XYZ")
        assert (env == EnvironmentType.UNKNOWN)

    def test_image_store(self):
        str = dbsetup.image_store(EnvironmentType.DEV)
        assert(str == '/mnt/image_files')
        str = dbsetup.image_store(EnvironmentType.PROD)
        assert(str == '/mnt/gcs-photos')
        str = dbsetup.image_store(EnvironmentType.UNKNOWN)
        assert(str is None)

    def test_ping_connection(self):
        dbsetup.ping_connection(None, True)

