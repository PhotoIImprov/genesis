from unittest import TestCase
import dbsetup
from dbsetup import EnvironmentType
import os

class TestDBsetup(TestCase):
    def test_connection_string(self):
        cs = dbsetup.connection_string(EnvironmentType.DEV)
        if os.name == 'nt': # ultraman
            assert (cs == "mysql+pymysql://python:python@localhost:3306/imageimprov")
        else:
            assert(cs == "mysql+pymysql://python:python@192.168.1.16:3306/imageimprov")
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
        if os.name == 'nt': # ultraman
            assert(str == 'c:/dev/image_files')
        else:
            assert(str == '/mnt/image_files')
        str = dbsetup.image_store(EnvironmentType.PROD)
        assert(str == '/mnt/gcs-photos')
        str = dbsetup.image_store(EnvironmentType.UNKNOWN)
        assert(str is None)

    def test_ping_connection(self):
        dbsetup.ping_connection(None, True)

    def test_template_dir(self):
        template_dir = dbsetup.template_dir(dbsetup.EnvironmentType.DEV)
        hostname = dbsetup.determine_host()
        if os.name == 'nt':
            if (hostname == 'ULTRAMAN'):
                assert (template_dir == 'c:/dev/genesis/templates')
            elif (hostname == '4KOFFICE'):
                assert(template_dir == 'C:/Users/bp100/PycharmProjects/genesis/templates')
        else:
            assert(template_dir == '/home/hcollins/dev/genesis/templates')

        template_dir = dbsetup.template_dir(dbsetup.EnvironmentType.PROD)
        assert(template_dir == '/home/bp100a/genesis/templates')

    def test_base_url(self):
        base_url = dbsetup.root_url(dbsetup.EnvironmentType.DEV)
        assert(base_url == 'http://localhost:8080')

        base_url = dbsetup.root_url(dbsetup.EnvironmentType.PROD)
        assert(base_url == 'https://api.imageimprov.com')
