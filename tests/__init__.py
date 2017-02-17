# Unit Test initialization
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import Session
import initschema
from dbsetup import Base, _connection_string
from unittest import TestCase

def setup_module():
    global transaction, connection, engine

    # Connect to the database and create the schema within a transaction
    engine = create_engine(_connection_string)
    connection = engine.connect()
    transaction = connection.begin()
    Base.metadata.create_all(connection)

    # If you want to insert fixtures to the DB, do it here

def teardown_module():
    # Roll back the top level transaction and disconnect from the database
    transaction.rollback()
    connection.close()
    engine.dispose()


class DatabaseTest(TestCase):
    def setup(self):
        self.__transaction = connection.begin_nested()
        self.session = Session(connection)

    def teardown(self):
        self.session.close()
        self.__transaction.rollback()

    @classmethod
    def setUpClass(cls):
        super(DatabaseTest, cls).setUpClass()
        setup_module()

    @classmethod
    def tearDownClass(cls):
        super(DatabaseTest, cls).tearDownClass()
        teardown_module()

