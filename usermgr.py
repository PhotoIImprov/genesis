from passlib.hash      import pbkdf2_sha256
from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base, engine, metadata
import hashlib

class AnonUser(Base):
    __tablename__ = "anonuser"
    id           = Column(Integer, primary_key = True, autoincrement=True)
    guid         = Column(String(32), nullable=False, unique=True)
    create_date  = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    @classmethod
    def find_anon_user(self, session, m_guid):
        if session is None or m_guid is None:
            return None

        self.guid = m_guid.upper()
        au = session.query(AnonUser).filter_by(guid = m_guid).first()
        return au

    @classmethod
    def create_anon_user(self, session, m_guid):

        if session is None or m_guid is None:
            return False

        m_guid = m_guid.upper()

        # First check if guid exists in the database
        au = self.find_anon_user(session, m_guid)
        if au:
            return False

        # this guid doesn't exist, so create the record
        session.add(self)
        session.commit()

        return True

    def get_id(self):
        return self.id

class User(Base):

    __tablename__ = 'userlogin'

    id           = Column(Integer, ForeignKey("anonuser.id"), primary_key = True)  # ties us back to our anon_user record
    hashedPWD    = Column(String(200), nullable=False)
    emailaddress = Column(String(200), nullable=False, unique=True)
    screenname   = Column(String(100), nullable=True)
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )


    @classmethod
    def __str__(self):
        return "User(id='%s')" % self.id

    @classmethod
    def find_user_by_id(self, session, m_id):
        self.id = id
        u = session.query(User).filter_by(id = m_id).first()
        return u

    @classmethod
    def find_user_by_email(self, session, m_emailaddress):
        # Does the user already exist?
        u = session.query(User).filter_by(emailaddress = m_emailaddress).first()

        if u is None:
            return None
        else:
            return u

    @classmethod
    def change_password(self, session, password):
        self.hashedPWD = pbkdf2_sha256.encrypt(password, rounds=1000, salt_size=16)
        session.commit()

    @classmethod
    def create_user(self, session, guid, username, password):
        # first need to see if user (emailaddress) already exists

        # quick & dirty validation of the email
        if '@' not in username:
            return None

        # now hash the password
        self.hashedPWD    = pbkdf2_sha256.encrypt(password, rounds=1000, salt_size=16)
        self.screenname   = None
        self.emailaddress = username
        self.id           = None

        # first lets see if this user already exists
        u_exists = self.find_user_by_email(session, self.emailaddress)
        if (u_exists is not None):
            return None

        # Find the anon account associated with this
        au = AnonUser().find_anon_user(session, guid)

        if au is None:
            return None

        self.id = au.get_id()

        # Now write the new users to the database
        session.add(self)
        session.commit()

        return self

def is_guid(m_guid, m_hash):
    # okay we have a suspected guid/hash combination
    # let's figure out if this is a guid by checking the
    # hash
    hashed_guid = hashlib.sha224(m_guid.encode('utf-8')).hexdigest()
    if (hashed_guid == m_hash):
        return True

    return False

# This is where all authentication calls come, we need to validate the user
def authenticate(username, password):
    # use the username (email) to lookup the passowrd and compare
    # after we hash the one we were sent
    if is_guid(username, password):
        # this is a guid, see if it's in our database
        foundAnonUser = AnonUser.find_anon_user(Session(), username)
        if foundAnonUser is not None:
            return foundAnonUser
    else:
        foundUser = User().find_user_by_email(Session(), username)

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
    u = User().find_user_by_id(Session(), user_id)

    # if u doesn't exist, that's really bad, it's a corrupted token or something
    # really strange. We should log this
    return u
