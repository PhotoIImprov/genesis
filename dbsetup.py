from sqlalchemy        import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm    import sessionmaker
from enum import Enum
import os
import logging
from flask import request

class ImageType(Enum):
    UNKNOWN = 0
    JPEG    = 1
    PNG     = 2
    BITMAP  = 3
    TIFF    = 4

class EnvironmentType(Enum):
    NOTSET  = -1
    UNKNOWN = 0
    DEV     = 1
    QA      = 2
    STAGE   = 3
    PROD    = 4

def determine_environment(hostname):
    if hostname is None:
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

    if environment is None:
        environment = determine_environment(None)
    if environment == EnvironmentType.DEV:
        return 'mysql+pymysql://python:python@192.168.1.149:3306/imageimprov'

    if environment == EnvironmentType.PROD:
        return 'mysql+pymysql://python:python@104.196.212.140:3306/imageimprov'

    raise

def image_store(environment):
    if environment == EnvironmentType.DEV:
        return '/mnt/image_files'

    if environment == EnvironmentType.PROD:
        return '/mnt/gcs-photos'

    return None

def is_gunicorn():
    _is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")
    return _is_gunicorn

def log_error(req, err_msg, uid):
    d = {'clientip': req.remote_addr, 'user': uid}
    logger.error('Error: %s', err_msg, extra=d)

# see what environment we are running on


# connection to MySQL instance on 4KOffice (intranet)
engine   = create_engine(connection_string(None), echo=False)
Session  = sessionmaker(bind=engine)
Base     = declarative_base()
metadata = Base.metadata

metadata.create_all(bind=engine, checkfirst=True)

# format for logging information
LOGGING_FORMAT = '%(asctime)-15s %(clientip)s %(user)-8s %(message)s'
LOGGING_LEVEL = logging.ERROR

logger = logging.getLogger(__name__)
logging.basicConfig(level=LOGGING_LEVEL, format=LOGGING_FORMAT)

# just for fun
QUOTES = (
    ('He was a wise man who invented beer.', 'Plato'),
    ('Beer is made by men, wine by God.', 'Martin Luther'),
    ('Who cares how time advances? I am drinking ale today.', 'Edgar Allen Poe'),
    ('It takes beer to make thirst worthwhile.', 'German proverb'),
    ('Beer: So much more than just a breakfast drink.', 'Homer Simpson'),
    ('History flows forward on a river of beer.', 'Anonymous'),
    ('Work is the curse of the drinking classes.', 'Oscar Wilde'),
    ('For a quart of ale is a dish for a king.', 'William Shakespeare, "A Winter\'s Tale"'),
    ('Beer. Now there\'s a temporary solution.', 'Homer Simpson'),
    ('What care I how time advances? I am drinking ale today', 'Edgar Allen Poe'),
    ('Beer, if drunk in moderation, softens the temper, cheers the spirit and promotes health', 'Thomas Jefferson'),
    ('In a study, scientists report that drinking beer can be good for the liver. I\'m sorry, did I say scientists? I mean Irish people', 'Tina Fey'),
    ('Most people hate the taste of beer - to being with. It is, however, a prejudice.', 'Winston Churchill'),
    ('For a quart of Ale is a dish for a king', 'William Shakespeare'),
    ('I am a firm believer in the people. If given the truth, they can be depended upon to meet any national crisis. The great point is to bring them the real facts, and beer', 'Abraham Lincoln'),
    ('Whoever drinks beer, he is quick to sleep; whoever sleeps long, does not sin; whoever does not sin, enters Heaven! Thus, let us drink beer!', 'Martin Luther')
)
