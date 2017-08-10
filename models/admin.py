from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, String, Boolean
from dbsetup import Base
from logsetup import logger
from uuid import uuid4
import urllib.parse
from datetime import datetime, timedelta
from models import usermgr
import requests
import sqlalchemy.orm
from typing import Type

class BaseURL(Base):
    __tablename__ = 'baseurl'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(255), nullable=False, index=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True,
                          server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    # ======================================================================================================
    @staticmethod
    def default_url() -> str:
        return 'https://api.imageimprov.com/'

    @staticmethod
    def get_url(session: sqlalchemy.orm.session, id: int) -> str:
        bu = session.query(BaseURL).get(id)
        if bu is not None:
            return bu.url

        # user doesn't have anything special mapped for them,
        # so return the default URL
        return default_url()

class CSRFevent(Base):
    __tablename__ = "csrftoken"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_csrftoken_uid"), nullable=False)

    csrf = Column(String(100), unique=True, nullable=False)
    been_used = Column(Boolean, default=False, nullable=False)
    expiration_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True,
                          server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, uid: int, expiration_hours: int) -> None:
        self.user_id = uid
        self.expiration_date = datetime.now()  + timedelta(hours=expiration_hours)
        self.csrf = self.generate_csrf_token()

    def generate_csrf_token(self) -> str:
        '''
        A random string of bytes that can be safely encoded in a URL
        :return:
        '''
        csrf = str(uuid4()).upper().translate({ord(c): None for c in '-'})
        url_safe_csrf = urllib.parse.quote_plus(csrf)
        return url_safe_csrf


class ForgotPassword():
    def send_password_email(self, emailaddress: str, csrf: str) -> int:
        """
        Send a link to the user where they can reset their password. The token
        ensures what account is being reset.
        :param emailaddress:
        :param csrf:
        :return:
        """
        mailgun_APIkey = 'key-6896c65db1a821c6e15ae34ae2ad94e9'  # shh! this is a secret
        mailgun_SMTPpwd = 'e2b0c198a98ebf1f1a338bb4046352a1'
        mailgun_baseURL = 'https://api.mailgun.net/v3/api.imageimprov.com/messages'
        mail_body = "click on this link to reset your password: https://www.imageimprov.com/forgotpassword?token={0}".format(csrf)

        res = requests.post(mailgun_baseURL,
                            auth=("api", mailgun_APIkey),
                            data={"from": "Forgot Password <noreply@imageimprov.com>",
                                  "to": emailaddress,
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

    def forgot_password(self, session: sqlalchemy.orm.session, u) -> int:
        '''
        User has forgotten their password, generate an email with a link so
        they can reset it.
        :param session:
        :param u: user object
        :return: HTTP status, =200 OK, all else is an error
        '''
        try:
            csrf_event = CSRFevent(u.id, 24)
            session.add(csrf_event)
            session.commit()
            http_status = self.send_password_email(u.emailaddress, csrf_event.csrf)
        except Exception as e:
            http_status = 500
        finally:
            session.close()
            return http_status

