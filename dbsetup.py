"""This contains miscellaneous setup, particularly related to the database"""
import os
from enum import Enum
from sqlalchemy        import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm    import sessionmaker
from sqlalchemy import exc
from sqlalchemy import event
from sqlalchemy import select


class ImageType(Enum):
    """the type of the image so we can process it"""
    UNKNOWN = 0
    JPEG = 1
    PNG = 2
    BITMAP = 3
    TIFF = 4


class EnvironmentType(Enum):
    """shorthand for the types of environments we might run in"""
    NOTSET = -1
    UNKNOWN = 0
    DEV = 1
    QA = 2
    STAGE = 3
    PROD = 4


class Configuration():
    """a class to wrap up our configuration information"""
    UPLOAD_CATEGORY_PICS = 4


def determine_host():
    """get our computer host name, in a Windows & Linux
    compatible manner"""
    hostname = 'unknown'
    try:
        hostname = str.upper(os.uname()[1])
    except AttributeError as e:
        hostname = str.upper(os.environ['COMPUTERNAME'])

    return hostname


def determine_environment(hostname):
    """figure out what environment we are running in"""
    if hostname is None:
        hostname = determine_host()

    if "DEV" in hostname:
        return EnvironmentType.DEV
    if "4KOFFICE" in hostname:
        return EnvironmentType.DEV
    if "ULTRAMAN" in hostname:
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
    """create the connection string to the database
    this is environment & machine dependent"""
    if environment is None:
        environment = determine_environment(None)
    if environment == EnvironmentType.DEV:
        if os.name == 'nt': # ultraman or 4KOFFICE
            return 'mysql+pymysql://python:python@localhost:3306/imageimprov'
        return 'mysql+pymysql://python:python@192.168.1.16:3306/imageimprov'

    if environment == EnvironmentType.PROD:
        return 'mysql+pymysql://python:python@127.0.0.1:3306/imageimprov'

    return None


def get_fontname(environment):
    """get the name of the font to use, environment specific"""
    if environment == EnvironmentType.DEV:
        if os.name == 'nt': # ultraman or 4KOFFICE
            return 'c:/Windows/Boot/Fonts/segmono_boot.ttf'
        return '/usr/share/fonts/truetype/ubuntu-font-family/UbuntuMono-B.ttf'

    if environment == EnvironmentType.PROD:
        return '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'

    return None


def resource_files(environment):
    """get environment specific location of resource images"""
    host = determine_host()
    if environment == EnvironmentType.DEV:
        if os.name == 'nt': # ultraman
            if host == 'ULTRAMAN':
                return 'c:/dev/genesis/photos'
            if host == '4KOFFICE':
                return 'c:/Users/bp100/PycharmProjects/genesis/photos'
        return '/home/hcollins/dev/genesis/photos'

    if environment == EnvironmentType.PROD:
        return '/home/bp100a/genesis/photos'

    return None


def image_store(environment: EnvironmentType) -> str:
    """find out where we should store images, it's environment dependent"""
    host = determine_host()
    if environment is None:
        environment = determine_environment(hostname=host)
    if environment == EnvironmentType.DEV:
        if os.name == 'nt': # ultraman
            return 'c:/dev/image_files'
        return '/mnt/image_files'

    if environment == EnvironmentType.PROD:
        return '/mnt/gcs-photos'

    return None

def photo_dir(environment: EnvironmentType) -> str:
    """find out where we find our photo data, environment dependent"""
    hostname = determine_host()
    if environment is None:
        environment = determine_environment(hostname)

    if environment == EnvironmentType.DEV:
        if hostname == 'ULTRAMAN':
            return 'c:/dev/genesis/photos'
        if hostname == '4KOFFICE':
            return 'C:/Users/bp100/PycharmProjects/genesis/photos'
        return '/home/hcollins/dev/genesis/photos'

    if environment == EnvironmentType.PROD:
        return '/home/bp100a/genesis/photos'

    return None

def template_dir(environment: EnvironmentType) -> str:
    """find out where we read our templates from, environment dependent"""
    hostname = determine_host()
    if environment is None:
        environment = determine_environment(hostname)

    if environment == EnvironmentType.DEV:
        if hostname == 'ULTRAMAN':
            return 'c:/dev/genesis/templates'
        if hostname == '4KOFFICE':
            return 'C:/Users/bp100/PycharmProjects/genesis/templates'
        return '/home/hcollins/dev/genesis/templates'

    if environment == EnvironmentType.PROD:
        return '/home/bp100a/genesis/templates'

    return None


def root_url(environment: EnvironmentType) -> str:
    """return the rootl url for the REST API entry point"""
    if environment is None:
        environment = determine_environment(None)

    if environment == EnvironmentType.DEV:
        return 'http://localhost:8080'

    if environment == EnvironmentType.PROD:
        return 'https://api.imageimprov.com'

    return None

def is_gunicorn() -> bool:
    """determine if we are running under gunicorn"""
    _is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")
    return _is_gunicorn

ENGINE = create_engine(connection_string(None), echo=False, pool_recycle=3600)
Session = sessionmaker(bind=ENGINE)
Base = declarative_base()
METADATA = Base.metadata
METADATA.create_all(bind=ENGINE, checkfirst=True)
_DEBUG = False


@event.listens_for(ENGINE, "engine_connect")
def ping_connection(connection, branch):
    """this listens for SQLAlchemy events and manages connections"""
    if branch:
        # "branch" refers to a sub-connection of a connection,
        # we don't want to bother pinging on these.
        return

    # turn off "close with result".  This flag is only used with
    # "connectionless" execution, otherwise will be False in any case
    save_should_close_with_result = connection.should_close_with_result
    connection.should_close_with_result = False

    try:
        # run a SELECT 1.   use a core select() so that
        # the SELECT of a scalar value without a table is
        # appropriately formatted for the backend
        connection.scalar(select([1]))
    except exc.DBAPIError as err:
        # catch SQLAlchemy's DBAPIError, which is a wrapper
        # for the DBAPI's exception.  It includes a .connection_invalidated
        # attribute which specifies if this connection is a "disconnect"
        # condition, which is based on inspection of the original exception
        # by the dialect in use.
        if err.connection_invalidated:
            # run the same SELECT again - the connection will re-validate
            # itself and establish a new connection.  The disconnect detection
            # here also causes the whole connection pool to be invalidated
            # so that all stale connections are discarded.
            connection.scalar(select([1]))
        else:
            raise
    finally:
        # restore "close with result"
        connection.should_close_with_result = save_should_close_with_result

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
    ('Most people hate the taste of beer - to begin with. It is, however, a prejudice.', 'Winston Churchill'),
    ('For a quart of Ale is a dish for a king', 'William Shakespeare'),
    ('I am a firm believer in the people. If given the truth, they can be depended upon to meet any national crisis. The great point is to bring them the real facts, and beer', 'Abraham Lincoln'),
    ('Whoever drinks beer, he is quick to sleep; whoever sleeps long, does not sin; whoever does not sin, enters Heaven! Thus, let us drink beer!', 'Martin Luther'),
    ('Milk is for babies. When you grow up you have to drink beer', 'Arnold Schwarzenegger'),
    ('I look like the kind of guy that has a bottle of beer in my hand', 'Charles Bronson'),
    ('Yes, sir. I\'m a real Souther boy. I got a red neck, white socks, and a BlueRibbon beer.', 'Billy Carter'),
    ('Give a man a beer, waste an hour. Teach a man to brew, and waste a lifetime!', 'Bill Owen'),
    ('He was a wise man who invented beer.', 'Plato'),
    ('Beer\'s intellectual. What a shame so many idiots drink it.', 'Ray Bradbury'),
    ('Beer is proof that God loves us and wants us to be happy', 'Benjamin Franklin'),
    ('You can\'t be a real country unless you have a beer and an airline - it helps if you have some kind of football team, or some nuclear weapons, but in the very least you need a beer', 'Frank Zappa'),
    ('The best beer in the world is the one in my hand', 'Charles Papazian'),
    ('Give my people plenty of beer, good beer, and cheap beer, and you will have no revolution among them', 'Queen Victoria'),
    ('Keep your libraries, your penal institutions, your insane asylums… give me beer. You think man needs rule, he needs beer. The world does not need morals, it needs beer… The souls of men have been fed with  indigestibles, but the soul could make use of beer.', 'Henry Miller')
)
