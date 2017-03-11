import sqlalchemy
from sqlalchemy        import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import DDL
from sqlalchemy.orm    import sessionmaker
from enum import Enum
import os

class ImageType(Enum):
    UNKNOWN = 0
    JPEG    = 1
    PNG     = 2
    BITMAP  = 3
    TIFF    = 4

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
    if "INSTANCE" in hostname:
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
        return 'mysql+pymysql://python:python@104.196.212.140:3306/imageimprov'

    return None

def image_store(environment):
    if environment == EnvironmentType.DEV:
        return '/mnt/image_files'

    if environment == EnvironmentType.PROD:
        return '/mnt/gcs-photos'

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

metadata.create_all(bind=engine, checkfirst=True)

