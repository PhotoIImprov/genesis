from passlib.hash      import pbkdf2_sha256
from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base
import hashlib

class AnonUser(Base):
    __tablename__ = "anonuser"
    id           = Column(Integer, primary_key = True, autoincrement=True)
    guid         = Column(String(32), nullable=False, unique=True)
    created_date  = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    @staticmethod
    def find_anon_user(session, m_guid):
        if session is None or m_guid is None:
            return None

        m_guid = m_guid.upper()
        au = session.query(AnonUser).filter_by(guid = m_guid).first()
        return au

    @staticmethod
    def create_anon_user(session, m_guid):

        if session is None or m_guid is None:
            return False

        m_guid = m_guid.upper()

        # First check if guid exists in the database
        au = AnonUser.find_anon_user(session, m_guid)
        if au is not None:
            return au

        # this guid doesn't exist, so create the record
        au = AnonUser()
        au.guid = m_guid

        session.add(au)
        session.commit()

        return au

    def get_id(self):
        return self.id

    @staticmethod
    def is_guid(m_guid, m_hash):
        # okay we have a suspected guid/hash combination
        # let's figure out if this is a guid by checking the
        # hash
        hashed_guid = hashlib.sha224(m_guid.encode('utf-8')).hexdigest()
        if (hashed_guid == m_hash):
            return True

        return False

class User(Base):

    __tablename__ = 'userlogin'

    id           = Column(Integer, ForeignKey("anonuser.id"), primary_key = True)  # ties us back to our anon_user record
    hashedPWD    = Column(String(200), nullable=False)
    emailaddress = Column(String(200), nullable=False, unique=True)
    screenname   = Column(String(100), nullable=True)
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    @classmethod
    def get_id(self):
        return self.id

    @classmethod
    def __str__(self):
        return "User(id='%s')" % self.id

    @staticmethod
    def find_user_by_id(session, m_id):
        q = session.query(User).filter_by(id = m_id)
        u = q.first()
        return u

    @staticmethod
    def find_user_by_email(session, m_emailaddress):
        # Does the user already exist?
        u = session.query(User).filter_by(emailaddress = m_emailaddress).first()
        return u

    @classmethod
    def change_password(self, session, password):
        self.hashedPWD = pbkdf2_sha256.encrypt(password, rounds=1000, salt_size=16)
        session.commit()

    @staticmethod
    def create_user(session, guid, username, password):
        # first need to see if user (emailaddress) already exists

        # quick & dirty validation of the email
        if '@' not in username:
            return None

        # Find the anon account associated with this
        au = AnonUser.find_anon_user(session, guid)
        if au is None:
            return None # this shouldn't happen

        # first lets see if this user already exists
        u_exists = User.find_user_by_email(session, username)
        if (u_exists is not None):
            return u_exists # this shouldn't happen!

        # okay, we can create a new UserLogin entry
        new_user = User()
        new_user.hashedPWD = pbkdf2_sha256.encrypt(password, rounds=1000, salt_size=16)
        new_user.emailaddress = username
        new_user.id = au.get_id()

        # Now write the new users to the database
        session.add(new_user)
        session.commit()

        return new_user

#
# JWT Callbacks
#
# This is where all authentication calls come, we need to validate the user
def authenticate(username, password):
    # use the username (email) to lookup the passowrd and compare
    # after we hash the one we were sent
    if AnonUser.is_guid(username, password):
        # this is a guid, see if it's in our database
        foundAnonUser = AnonUser.find_anon_user(Session(), username)
        if foundAnonUser is not None:
            return foundAnonUser
    else:
        foundUser = User.find_user_by_email(Session(), username)

        if foundUser is not None:
            # time to check the password
            if (pbkdf2_sha256.verify(password, foundUser.hashedPWD)):
                return foundUser

    return None

# subsequent calls with JWT payload call here to confirm identity
def identity(payload):
    # called with decrypted payload to establish identity
    # based on a user id
    user_id = payload['identity']
    u = User.find_user_by_id(Session(), user_id)

    # if u doesn't exist, that's really bad, it's a corrupted token or something
    # really strange. We should log this
    return u
