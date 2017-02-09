from passlib.hash      import pbkdf2_sha256
from sqlalchemy        import Column, Integer, String, DateTime, text
from dbsetup           import Session, Base, engine, metadata

class User(Base):

    __tablename__ = 'userlogin'

    id           = Column(Integer, primary_key = True, autoincrement=True)
    hashedPWD    = Column(String(200), nullable=False)
    emailaddress = Column(String(200), nullable=False, unique=True)
    screenname   = Column(String(100), nullable=True)
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )


#    def __init__(self, id, username, password):
#        self.id           = id
#        self.screenname   = username
#        self.hashedPWD    = pbkdf2_sha256.encrypt(password, rounds=1000, salt_size=16)
#        self.emailaddress = self.screenname + '@hotmail.com'

    def __str__(self):
        return "User(id='%s')" % self.id

    def FindUserById(self, session, id):
        self.id = id
        q = session.query(User).filter(User.id == self.id)
        u = q.all()

        if not u:
            return None
        else:
            return u[0]

    def FindUserByEmail(self, session, emailaddress):
        # Does the user already exist?
        self.emailaddress = emailaddress
        q = session.query(User).filter(User.emailaddress == self.emailaddress)
        u = q.all()

        if not u:
            return None
        else:
            return u[0]

    def ChangePassword(self, password):
        self.hashedPWD = pbkdf2_sha256.encrypt(password, rounds=1000, salt_size=16)

    def CreateUser(self, session, username, password):
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
        u_exists = self.FindUserByEmail(session, self.emailaddress)
        if (u_exists is None):
            # Now write the new users to the database
            session.add(self)
            session.commit()
        else:
            return None #self.__dict__.update(u_exists.__dict__)

        return self

# This is where all authentication calls come, we need to validate the user
def authenticate(username, password):
    # use the username (email) to lookup the passowrd and compare
    # after we hash the one we were sent
    foundUser = User().FindUserByEmail(Session(), username)

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
    u = User().FindUserByID(Session(), user_id)

    # if u doesn't exist, that's really bad, it's a corrupted token or something
    # really strange. We should log this
    return u

