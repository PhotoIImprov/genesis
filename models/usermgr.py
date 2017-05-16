from passlib.hash      import pbkdf2_sha256
from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base
import hashlib
import pymysql
from logsetup import logger

class AnonUser(Base):
    __tablename__ = "anonuser"
    id            = Column(Integer, primary_key = True, autoincrement=True)
    guid          = Column(String(32), nullable=False, unique=True)
    created_date  = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    @staticmethod
    def find_anon_user(session, m_guid):
        if session is None or m_guid is None:
            return None

        m_guid = m_guid.upper().translate({ord(c): None for c in '-'})
        au = None
        try:
            au = session.query(AnonUser).filter_by(guid = m_guid).first()
        except Exception as e:
            logger.exception(msg='error finding anonymous user {}'.format(m_guid))
            raise
        finally:
            return au

    @staticmethod
    def get_anon_user_by_id(session, anon_id):
        if session is None or anon_id is None:
            return None

        # okay, use the supplied id to lookup the Anon User record
        au = session.query(AnonUser).filter_by(id = anon_id).first()
        return au

    @staticmethod
    def create_anon_user(session, m_guid):

        if session is None or m_guid is None:
            return False

        # make uppercase, strip out hyphens
        m_guid = m_guid.upper().translate({ord(c): None for c in '-'})

        # First check if guid exists in the database
        au = AnonUser.find_anon_user(session, m_guid)
        if au is not None:
            return au

        # this guid doesn't exist, so create the record
        au = AnonUser()
        au.guid = m_guid

        session.add(au)
        return au

    def get_id(self):
        return self.id

    @staticmethod
    def is_guid(m_guid, m_hash):
        # okay we have a suspected guid/hash combination
        # let's figure out if this is a guid by checking the
        # hash
        hashed_guid = hashlib.sha224(m_guid.encode('utf-8')).hexdigest()
        if hashed_guid == m_hash:
            return True

        return False

class User(Base):

    __tablename__ = 'userlogin'

    id           = Column(Integer, ForeignKey("anonuser.id", name="fk_userlogin_id"), primary_key = True)  # ties us back to our anon_user record
    hashedPWD    = Column(String(200), nullable=False)
    emailaddress = Column(String(200), nullable=False, unique=True)
    screenname   = Column(String(100), nullable=True, unique=True)
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    @staticmethod
    def find_user_by_id(session, m_id):
        q = session.query(User).filter_by(id = m_id)
        u = q.first()
        return u

    @staticmethod
    def find_user_by_email(session, m_emailaddress):
        # Does the user already exist?
        q = session.query(User).filter_by(emailaddress = m_emailaddress)
        u = q.first()
        return u

    def change_password(self, session, password):
        self.hashedPWD = pbkdf2_sha256.encrypt(password, rounds=1000, salt_size=16)

    @staticmethod
    def create_user(session, guid, username, password):
        # first need to see if user (emailaddress) already exists

        # quick & dirty validation of the email
        if '@' not in username:
            return None

        # Find the anon account associated with this
        au = AnonUser.find_anon_user(session, guid)
        if au is None:
            au = AnonUser.create_anon_user(session, guid)

        # first lets see if this user already exists
        u_exists = User.find_user_by_email(session, username)
        if u_exists is not None:
            return u_exists # this shouldn't happen! (probably should delete anon user if we just created one - transaction!)

        # okay, we can create a new UserLogin entry
        new_user = User()
        new_user.hashedPWD = pbkdf2_sha256.encrypt(password, rounds=1000, salt_size=16)
        new_user.emailaddress = username
        new_user.id = au.get_id()

        # Now write the new users to the database
        session.add(new_user)
        return new_user

#
# JWT Callbacks
#
# This is where all authentication calls come, we need to validate the user
def authenticate(username, password):
    # use the username (email) to lookup the passowrd and compare
    # after we hash the one we were sent
    session = Session()
    if AnonUser.is_guid(username, password):
        # this is a guid, see if it's in our database after we normalize it
        guid = username.upper().translate({ord(c): None for c in '-'})
        foundAnonUser = AnonUser.find_anon_user(session, guid)
        session.close()
        return foundAnonUser
    else:
        foundUser = User.find_user_by_email(session, username)
        session.close()
        if foundUser is not None:
            if pbkdf2_sha256.verify(password, foundUser.hashedPWD):
                return foundUser

    return None

# subsequent calls with JWT payload call here to confirm identity
def identity(payload):
    # called with decrypted payload to establish identity
    # based on a user id
    user_id = payload['identity']
    session = Session()
    au = AnonUser.get_anon_user_by_id(session, user_id)
    session.close()
    return au

#================================= F R I E N D - L I S T ========================================
class Friend(Base):

    __tablename__ = 'friend'

    user_id      = Column(Integer, ForeignKey("anonuser.id", name="fk_friend_user_id"),     primary_key = True)  # ties us back to our user record
    myfriend_id  = Column(Integer, ForeignKey("anonuser.id", name="fk_friend_myfriend_id"), primary_key = True)  # ties us back to our user record
    active       = Column(Integer, nullable=False, default=1)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    @staticmethod
    def is_friend(session, uid, maybe_friend_uid):
        # lookup and see if this person is a friend!
        q = session.query(Friend).filter(Friend.user_id == uid).filter(Friend.myfriend_id == maybe_friend_uid).filter(Friend.active == 1)
        f = q.one_or_none()
        return f is not None

class FriendRequest(Base):

    __tablename__ = 'friendrequest'

    id                  = Column(Integer, primary_key = True, autoincrement=True)
    asking_friend_id    = Column(Integer, ForeignKey("anonuser.id", name="fk_askingfriend_id"), nullable=False)  # ties us back to our user record
    notifying_friend_id = Column(Integer, ForeignKey("anonuser.id", name="fk_notifyingfriend_id"), nullable=True)  # ties us back to our user record (if exists)
    friend_email        = Column(String(200), nullable=False)

    # declined  accepted
    # NULL      NULL        waiting for response
    #   1        x          friendship not accepted
    # NULL/0     1          friendship accepted
    #   x        0          friendship not accepted

    declined             = Column(Integer, nullable=True)
    accepted             = Column(Integer, nullable=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    def get_id(self):
        return self.id

    def __init__(self, uid, f_email):
        self.friend_email = f_email
        self.asking_friend_id = uid

    def find_notifying_friend(self, session):
        # see if the email of the friend is in our system
        fu = User.find_user_by_email(session, self.friend_email)
        if fu is not None:
            self.notifying_friend_id = fu.id

    @staticmethod
    def update_friendship(session, uid, fid, accept):
        if fid is None or session is None or uid is None:
            return

        # okay, get the friendship record..
        q = session.query(FriendRequest).filter_by(id = fid)
        fr = q.first()
        if fr is None:
            raise

        if fr.notifying_friend_id is not None and fr.notifying_friend_id == uid:
            raise # something wrong!!

        if accept:
            fr.accepted = True
            fr.declined = False
        else:
            fr.declined = True
            fr.accepted = False

        # let's create a record in the Friend table!
        new_friend = Friend()
        new_friend.user_id = fr.asking_friend_id
        new_friend.myfriend_id = uid
        new_friend.active = 1

        session.add(new_friend)
        return

