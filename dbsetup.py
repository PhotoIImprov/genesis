import sqlalchemy
from sqlalchemy        import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import DDL
from sqlalchemy.orm    import sessionmaker
from enum import Enum
import os

class EnvironmentType(Enum):
    UNKNOWN = 0
    DEV     = 1
    QA      = 2
    STAGE   = 3
    PROD    = 4

# initialize some configuration information
_environment       = EnvironmentType.UNKNOWN
_connection_string = None

def determine_environment():
    hostname = str.upper(os.uname()[1])
    if "DEV" in hostname:
        return EnvironmentType.DEV
    if "PROD" in hostname:
        return EnvironmentType.PROD
    if "STAGE" in hostname:
        return EnvironmentType.STAGE
    if "QA" in hostname:
        return EnvironmentType.QA

    return EnvironmentType.UNKNOWN

def connection_string(environment):

    if environment == EnvironmentType.DEV:
        return 'mysql+pymysql://python:python@192.168.1.149:3306/imageimprov'

    if environment == EnvironmentType.PROD:
        return 'mysql+pymysql://python:python@104.154.227.232:3306/imageimprov'

    return None

# see what environment we are running on
_environment = determine_environment()
_connection_string = connection_string(_environment)
_is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")

# connection to MySQL instance on 4KOffice (intranet)
engine   = create_engine(_connection_string, echo=False)
Session  = sessionmaker(bind=engine)
Base     = declarative_base()
metadata = Base.metadata

sqlalchemy.event.listen(metadata, 'before_create',
                        DDL('DROP FUNCTION IF EXISTS increment_photo_index;\n'
                            'CREATE FUNCTION increment_photo_index(cid int) RETURNS int\n'
                            'BEGIN\n'
                            'DECLARE x int;\n'
                            'update photoindex set idx = (@x:=idx)+1 where category_id = cid;\n'
                            'return @x;\n'
                            'END;'))

metadata.create_all(bind=engine, checkfirst=True)

