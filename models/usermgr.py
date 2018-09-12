"""User Manager. Contains classes to manage the user accounts, including login and creation"""
from typing import Type
import hashlib
import json
import uuid
from enum import Enum
from passlib.hash import pbkdf2_sha256
from sqlalchemy import Column, Integer, String, DateTime, text, ForeignKey, orm
from oauth2client import client
import httplib2
from flask import jsonify
from models import admin
from dbsetup import Session, Base
from logsetup import logger


class UserType(Enum):
    """We have 3 types of users, players are the most common,
    but reserved type for staff so we can filter out for analytics"""
    PLAYER = 0
    IIKNOWN = 1        # someone that imageimprov staff knows and doesn't want counted in reports
    IISTAFF = 2        # an imageimprove staff member that has special powers

    @staticmethod
    def to_str(type: int) -> str:
        if type == UserType.PLAYER.value:
            return "PLAYER"
        if type == UserType.IIKNOWN.value:
            return "iiKNOWN"
        if type == UserType.IISTAFF.value:
            return "iiSTAFF"
        return "INVALID"


class AnonUser(Base):
    """Users do not have to provide any information to register
    we have anonymous play. All users have a anonymous account that
    can be *upgraded* to a full user"""
    __tablename__ = "anonuser"
    id  = Column(Integer, primary_key= True, autoincrement=True)
    guid = Column(String(32), nullable=False, unique=True)
    base_id = Column(Integer, ForeignKey("baseurl.id", name="fk_anonuser_base_id"), nullable=True)
    usertype = Column(Integer, default=UserType.PLAYER.value)
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    def __init__(self, *args, **kwargs):
        self.id = kwargs.get('uid')

    @staticmethod
    def find_anon_user(session: orm.Session, m_guid: str):
        if session is None or m_guid is None:
            return None

        m_guid = m_guid.upper().translate({ord(c): None for c in '-'})
        anonymous_user = None
        try:
            anonymous_user = session.query(AnonUser).filter_by(guid = m_guid).first()
        except Exception as e:
            logger.exception(msg='error finding anonymous user {}'.format(m_guid))
            raise
        finally:
            return anonymous_user

    @staticmethod
    def get_anon_user_by_id(session: orm.Session, anonymous_user_id: int):
        if session is None or anonymous_user_id is None:
            return None

        # okay, use the supplied id to lookup the Anon User record
        anonymous_user = session.query(AnonUser).filter_by(id = anonymous_user_id).first()
        return anonymous_user

    @staticmethod
    def create_anon_user(session: orm.Session, m_guid: str):

        if session is None or m_guid is None:
            return False

        # make uppercase, strip out hyphens
        m_guid = m_guid.upper().translate({ord(c): None for c in '-'})

        # First check if guid exists in the database
        anonymous_user = AnonUser.find_anon_user(session, m_guid)
        if anonymous_user is not None:
            return anonymous_user

        # this guid doesn't exist, so create the record
        anonymous_user = AnonUser()
        anonymous_user.guid = m_guid

        session.add(anonymous_user)
        return anonymous_user

    @staticmethod
    def get_baseurl(session: orm.Session, uid: int) -> str:
        au = AnonUser.get_anon_user_by_id(session, uid)

        if au is not None and au.base_id is not None:
            b = session.query(admin.BaseURL).get(au.base_id)
            if b is not None:
                return b.url

        return 'https://api.imageimprov.com/'

    def get_id(self):
        return self.id

    @staticmethod
    def is_guid(m_guid: str, m_hash: str) -> bool:
        # okay we have a suspected guid/hash combination
        # let's figure out if this is a guid by checking the
        # hash
        hashed_guid = hashlib.sha224(m_guid.encode('utf-8')).hexdigest()
        if hashed_guid == m_hash:
            return True

        return False


class User(Base):

    __tablename__ = 'userlogin'

    id = Column(Integer, ForeignKey("anonuser.id", name="fk_userlogin_id"), primary_key = True)  # ties us back to our anon_user record
    hashedPWD = Column(String(200), nullable=False)
    emailaddress = Column(String(200), nullable=False, unique=True)
    screenname = Column(String(100), nullable=True, unique=True)
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    @staticmethod
    def find_user_by_id(session: orm.Session, m_id: int):
        query = session.query(User).filter_by(id = m_id)
        user = query.first()
        return user

    @staticmethod
    def find_user_by_email(session: orm.Session, m_emailaddress: str):
        # Does the user already exist?
        user = None
        try:
            query = session.query(User).filter_by(emailaddress = m_emailaddress)
            user = query.first()
        except Exception as e:
            return None

        return user

    def change_password(self, session: orm.Session, password: str) -> None:
        self.hashedPWD = pbkdf2_sha256.hash(password, rounds=1000, salt_size=16)

    # def forgot_password(self, session) -> int:
    #     '''
    #     User has forgotten their password, generate a new one
    #     update their record and email it to them.
    #     :param session:
    #     :return:
    #     '''
    #     try:
    #         new_password = self.random_password(8)
    #         self.change_password(session, new_password)
    #         http_status = self.send_password_email(new_password)
    #     except Exception as e:
    #         http_status = 500
    #     finally:
    #         return http_status

    @staticmethod
    def create_user(session: orm.Session, guid: str, username: str, password: str):
        """create a known user, so check to see if the username
        supplied is an email address. if there's an anonymous
        account already, then link that to the email account"""

        # quick & dirty validation of the email
        if '@' not in username:
            return None

        # Find the anon account associated with this
        anonymous_user = AnonUser.find_anon_user(session, guid)
        if anonymous_user is None:
            anonymous_user = AnonUser.create_anon_user(session, guid)

        # first lets see if this user already exists
        user_exists = User.find_user_by_email(session, username)
        if user_exists is not None:
            return user_exists # this shouldn't happen! (probably should delete anon user if we just created one - transaction!)

        # okay, we can create a new UserLogin entry
        new_user = User()
        new_user.hashedPWD = pbkdf2_sha256.hash(password, rounds=1000, salt_size=16)
        new_user.emailaddress = username
        new_user.id = anonymous_user.get_id()

        # Now write the new users to the database
        session.add(new_user)
        return new_user # return the "root" user, which is the anon users for this account

#
# JWT Callbacks
#
# This is where all authentication calls come, we need to validate the user
def authenticate(username: str, password: str):
    """authenticate the user via username/pasword
    we check for the method of authentication

    oAuth2 - if user is in the oAuth table then that is how
            we authenticate them.
    Anonymous User - these users only supply a UUID as their username
                    which we determine by comparing it to the hashed pwd
    Known User - these users have email address as the username and a
                real password
    """
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
        found_user = User.find_user_by_email(session, username)
        session.close()
        if found_user is not None:
            if pbkdf2_sha256.verify(password, found_user.hashedPWD):
                return found_user

    logger.debug(msg="[/auth] login failed for u:{0}, p:{1}".format(username, password))
    return None

# subsequent calls with JWT payload call here to confirm identity
def identity(payload: dict):
    """extract the user identifier from the JWT payload and find
    our user account"""
    # called with decrypted payload to establish identity
    # based on a user id
    user_id = payload['identity']
    session = Session()
    anonymous_user = AnonUser.get_anon_user_by_id(session, user_id)
    session.close()
    return anonymous_user

def auth_response_handler(access_token, identity):
    if isinstance(identity, User):
        return jsonify({'access_token': access_token.decode('utf-8'), 'email': identity.emailaddress})
    else:
        return jsonify({'access_token': access_token.decode('utf-8')})


#================================= o A u t h 2  =================================================
class UserAuth(Base):
    """
    A UserAuth record is tied to the AnonUser. There can be multiple UserAuth records, but only
    one per service provider. The presence of this record indicates that the service provider's
    associating to this user record has been validated.
    """
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
    def is_oAuth2(username: str, password: str) -> bool:
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

    def authenticate_user(self, session: orm.Session, oauth2_accesstoken, serviceprovider, debug_json=None):
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


class Friend(Base):
    """our class to manage tell-a-friend'"""
    __tablename__ = 'friend'

    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_friend_user_id"),     primary_key = True)  # ties us back to our user record
    myfriend_id  = Column(Integer, ForeignKey("anonuser.id", name="fk_friend_myfriend_id"), primary_key = True)  # ties us back to our user record
    active = Column(Integer, nullable=False, default=1)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    @staticmethod
    def is_friend(session: orm.Session, uid: int, maybe_friend_uid: int) -> bool:
        # lookup and see if this person is a friend!
        query = session.query(Friend).filter(Friend.user_id == uid)\
            .filter(Friend.myfriend_id == maybe_friend_uid)\
            .filter(Friend.active == 1)
        friend_request = query.one_or_none()
        return friend_request is not None

class FriendRequest(Base):
    """the actual friend request so we can track if the friend has accepted"""
    __tablename__ = 'friendrequest'

    id = Column(Integer, primary_key = True, autoincrement=True)
    asking_friend_id = Column(Integer, ForeignKey("anonuser.id", name="fk_askingfriend_id"), nullable=False)  # ties us back to our user record
    notifying_friend_id = Column(Integer, ForeignKey("anonuser.id", name="fk_notifyingfriend_id"), nullable=True)  # ties us back to our user record (if exists)
    friend_email = Column(String(200), nullable=False)

    # declined  accepted
    # NULL      NULL        waiting for response
    #   1        x          friendship not accepted
    # NULL/0     1          friendship accepted
    #   x        0          friendship not accepted

    declined = Column(Integer, nullable=True)
    accepted = Column(Integer, nullable=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    def get_id(self):
        """simple getter with current user id"""
        return self.id

    def __init__(self, user_id: int, friend_email: str):
        self.friend_email = friend_email
        self.asking_friend_id = user_id

    def find_notifying_friend(self, session: orm.Session) -> None:
        """see if we sent out a friendship notification"""
        # see if the email of the friend is in our system
        found_user = User.find_user_by_email(session, self.friend_email)
        if found_user is not None:
            self.notifying_friend_id = found_user.id

    @staticmethod
    def update_friendship(session, user_id: int, friend_request_id: int, accept: bool) -> None:
        """update the friendshipt request"""
        if friend_request_id is None or session is None or user_id is None:
            return

        # okay, get the friendship record..
        query = session.query(FriendRequest).filter_by(id=friend_request_id)
        friend_request = query.first()
        if friend_request is None:
            raise Exception("No Friend Request!")

        if friend_request.notifying_friend_id is not None and friend_request.notifying_friend_id == user_id:
            raise Exception("poorly structured friend request fid={0}".format(friend_request_id))

        if accept:
            friend_request.accepted = True
            friend_request.declined = False
        else:
            friend_request.declined = True
            friend_request.accepted = False

        # let's create a record in the Friend table!
        new_friend = Friend()
        new_friend.user_id = friend_request.asking_friend_id
        new_friend.myfriend_id = user_id
        new_friend.active = 1

        session.add(new_friend)
        return
