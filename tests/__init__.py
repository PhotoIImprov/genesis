# Unit Test initialization
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import Session
import initschema
from dbsetup import Base, connection_string, Session
from unittest import TestCase
import datetime
from flask import Flask, jsonify

# specify the JWT package's call backs for authentication of username/password
# and subsequent identity from the payload in the token
app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'imageimprove3077b47'

app.config['JWT_EXPIRATION_DELTA'] = datetime.timedelta(days=10)

def setup_module():
    global transaction, connection, engine

    # Connect to the database and create the schema within a transaction
    engine = create_engine(connection_string(None))
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
        self.session = Session() #Session(connection)

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

