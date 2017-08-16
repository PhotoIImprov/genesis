from passlib.hash      import pbkdf2_sha256
from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base
import hashlib
import pymysql
from logsetup import logger
from oauth2client import client
import oauth2client
import httplib2
import json
import uuid
from flask import jsonify
import string
import random
import requests
from models import admin

class AnonUser(Base):
    __tablename__ = "anonuser"
    id            = Column(Integer, primary_key = True, autoincrement=True)
    guid          = Column(String(32), nullable=False, unique=True)
    base_id       = Column(Integer, ForeignKey("baseurl.id", name="fk_anonuser_base_id"), nullable=True)
    usertype      = Column(Integer, default=0)
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

    @staticmethod
    def get_baseurl(session, uid: int) -> str:
        au = AnonUser.get_anon_user_by_id(session, uid)

        if au is not None and au.base_id is not None:
            b = session.query(admin.BaseURL).get(au.base_id)
            if b is not None:
                return b.url

        return 'https://api.imageimprov.com/'

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
        u = None
        try:
            q = session.query(User).filter_by(emailaddress = m_emailaddress)
            u = q.first()
        except Exception as e:
            return None

        return u

    def change_password(self, session, password: str) -> None:
        self.hashedPWD = pbkdf2_sha256.hash(password, rounds=1000, salt_size=16)

    def random_password(self, size: int) -> str:
        # define our character pool for randomness to avoid confusion
        char_pool = 'ABCDEFGHJKLMNPRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789+!'
        new_password = ''.join(random.choice(char_pool) for _ in range(size))
        return new_password

    def send_password_email(self, new_password: str) -> int:
        '''
        Send a "forgot password" email to a user. Their password has
        been re-generated and is totally random, it's "lost" after this email
        and only exists as a hash in the DB
        :param new_password: new password (already been set in DB!)
        :return:
        '''
        mailgun_APIkey = 'key-6896c65db1a821c6e15ae34ae2ad94e9' # shh! this is a secret
        mailgun_SMTPpwd = 'e2b0c198a98ebf1f1a338bb4046352a1'
        mailgun_baseURL = 'https://api.mailgun.net/v3/api.imageimprov.com/messages'
        mail_body = "new password = {0}".format(new_password)

        res = requests.post(mailgun_baseURL,
                            auth=("api", mailgun_APIkey),
                            data={"from": "Forgot Password <noreply@imageimprov.com>",
                                  "to": self.emailaddress,
                                  "subject": "Password reset",
                                  "text": mail_body})
        '''
            200 - Everything work as expected
            400 - Bad Request - often missing required parameter
            401 - Unauthorized - No valid API key provided
            402 - Request failed - parameters were valid but request failed
            404 - Not found - requested item doesn't exist
            500, 502, 503, 504 - Server Errors - something wrong on Mailgun's end
        '''
        return res.status_code

    def forgot_password(self, session) -> int:
        '''
        User has forgotten their password, generate a new one
        update their record and email it to them.
        :param session:
        :return:
        '''
        try:
            new_password = self.random_password(8)
            self.change_password(session, new_password)
            http_status = self.send_password_email(new_password)
        except Exception as e:
            http_status = 500
        finally:
            return http_status

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
        new_user.hashedPWD = pbkdf2_sha256.hash(password, rounds=1000, salt_size=16)
        new_user.emailaddress = username
        new_user.id = au.get_id()

        # Now write the new users to the database
        session.add(new_user)
        return new_user # return the "root" user, which is the anon users for this account

#
# JWT Callbacks
#
# This is where all authentication calls come, we need to validate the user
def authenticate(username, password):
    # use the username (email) to lookup the passowrd and compare
    # after we hash the one we were sent
    session = Session()
    if UserAuth.is_oAuth2(username, password):
        o = UserAuth()
        return o.authenticate_user(session, password, username)

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

    logger.debug(msg="[/auth] login failed for u:{0}, p:{1}".format(username, password))
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

def auth_response_handler(access_token, identity):
    if isinstance(identity, User):
        return jsonify({'access_token': access_token.decode('utf-8'), 'email': identity.emailaddress})
    else:
        return jsonify({'access_token': access_token.decode('utf-8')})

#================================= o A u t h 2  =================================================
class UserAuth(Base):
    '''
    A UserAuth record is tied to the AnonUser. There can be multiple UserAuth records, but only
    one per service provider. The presence of this record indicates that the service provider's
    associating to this user record has been validated.
    '''
    __tablename__ = 'userauth'

    id = Column(Integer, ForeignKey("anonuser.id", name="fk_userauth_id"), primary_key = True)  # ties us back to our anon_user record
    serviceprovider = Column(String(100), nullable=False, primary_key = True)
    sid = Column(String(100), nullable=True) # if the service provider provides a unique identifier, we can track it here
    token = Column(String(500), nullable=False, unique=True)
    version = Column(String(16), nullable=True, unique=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    _valid_serviceproviders = ('GOOGLE', 'FACEBOOK', 'FAKESERVICEPROVIDER')

    @staticmethod
    def is_oAuth2(username, password):
        """
        determine if the username/password is really a serviceprovider/token
        :param username:
        :param password:
        :return:
        """
        serviceprovider = username.upper()
        if not serviceprovider in UserAuth._valid_serviceproviders:
            return False

        # okay, the username is a serviceprovider name, let's do a check on the token...
        token = password
        return token is not None

    def __init__(self, *args, **kwargs):
        self.id = kwargs.get('uid')
        self.serviceprovider = kwargs.get('serviceprovider')
        if self.serviceprovider is not None:
            self.serviceprovider = self.serviceprovider.upper()
        self.token = kwargs.get('token')
        self.version = kwargs.get('version')
        self.sid = kwargs.get('serviceprovider_id')

    def authenticate_user(self, session, oauth2_accesstoken, serviceprovider, debug_json=None):
        """

        :param session:
        :param oauth2_accesstoken: string containing the oAuth2 token from the client
        :param serviceprovider: string of the service provider (i.e. "Facebook", "Google", "Twitter", etc.)
        :return:
        """
        if oauth2_accesstoken is None:
            logger.error(msg='access token is None!!')
            return None
        if serviceprovider is None:
            logger.error(msg='Invalid service provider = None')
            return None

        serviceprovider = serviceprovider.upper()
        if not serviceprovider in self._valid_serviceproviders:
            logger.error(msg='Invalid service provider = {0}'.format(serviceprovider))
            return None

        credentials = client.AccessTokenCredentials(oauth2_accesstoken, 'my-user-agent/1.0')
        http = httplib2.Http()
        http = credentials.authorize(http)
        serviceprovider_email = None
        serviceprovider_uid = None

        if serviceprovider == 'FAKESERVICEPROVIDER':
            if debug_json is not None:
                d = json.loads(debug_json.decode("utf-8"))
                serviceprovider_uid = d['id']
                serviceprovider_email = d['email']
            else:
                serviceprovider_email = 'fakeuser@fakeserviceprovider.com'
                serviceprovider_uid = 123456

        if serviceprovider == 'FACEBOOK':
            try:
                if debug_json is None:
                    response, content = http.request('https://graph.facebook.com/v2.9/me?fields=id,name,email', 'GET')
                    if response.status != 200:
                        return None
                else:
                    content = debug_json

                d = json.loads(content.decode("utf-8"))
                serviceprovider_uid = d['id']
                serviceprovider_email = d['email']
            except KeyError as ke:
                logger.info(msg="Facebook response missing key {0}".format(ke.args[0]))
                return None
            except Exception as e:
                logger.info(msg="Facebook token failed {0}".format(oauth2_accesstoken))
                return None

        if serviceprovider == 'GOOGLE':
            try:
                if debug_json is None:
                    response, content = http.request('https://www.googleapis.com/plus/v1/people/me', 'GET')
                    if response.status != 200:
                        return None
                else:
                    content = debug_json

                d = json.loads(content.decode("utf-8"))
                serviceprovider_uid = d['id']
                g_email_list = d['emails']
                for m in g_email_list:
                    if m['type'] == 'account':
                        serviceprovider_email = m['value']
                        break

            except Exception as e:
                msg = e.args[0]
                if msg == 'The access_token is expired or invalid and can\'t be refreshed.':
                    logger.info(msg=msg)
                    return None

                logger.info(msg="Google token failed {0}".format(oauth2_accesstoken))
                return None

        if serviceprovider_email is None:
            return None

        # See if this user is already registered
        au = User.find_user_by_email(session, serviceprovider_email)
        if au is not None:
            return au

        # This is the first time we have seen this user, so create an account for them
        try:
            guid = str(uuid.uuid1())
            guid = guid.upper().translate({ord(c): None for c in '-'})
            u = User.create_user(session, guid, serviceprovider_email, oauth2_accesstoken)
            session.commit()
            if u is not None:
                logger.info(msg='Created account for serviceprovider {0}, email {1}'.format(serviceprovider, serviceprovider_email))
            else:
                logger.error(msg='Error creating account for serviceprovider {0}, email {1}'.format(serviceprovider, serviceprovider_email))
            return u
        except Exception as e:
            logger.exception(msg="error oAuth2 user creation")
            session.rollback()
            return None

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

