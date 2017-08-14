from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, String, Boolean
from dbsetup import Base
import dbsetup
from logsetup import logger
from uuid import uuid4
import urllib.parse
from datetime import datetime, timedelta
import requests
import sqlalchemy.orm
import jinja2

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

    @staticmethod
    def get_csrfevent(session, token: str):
        q = session.query(CSRFevent).filter_by(csrf = token)
        ev = q.one()
        return ev

    def marked_used(self):
        self.been_used = True

    def isvalid(self)-> bool:
        '''
        we have a CSRFevent object from the database, is it still valid?

        :return:
        '''
        if self.been_used or self.expiration_date < datetime.now():
            return False

        return True

def read_template(template_name: str) -> str:
    '''
    read the named template in as string
    :param template_name:
    :return:
    '''
    base_dir = dbsetup.template_dir(environment=None)
    fname = base_dir + '/' + template_name
    try:
        fp = open(fname, 'r')
        template = fp.read()
        fp.close()
        return template
    except Exception as e:
        logger.exception(msg="problem openning template")
        raise

def send_forgot_password_email(emailaddress: str, csrf: str) -> int:
    """
    Send a link to the user where they can reset their password. The token
    ensures what account is being reset.
    :param emailaddress:
    :param csrf:
    :return:
    """

    mail_template = read_template("email/reset_password.html")
    root_url = dbsetup.root_url(environment=None)
    target_url = root_url + "/en-US/user/resetpassword.html?token={0}".format(csrf)

    rtemplate = jinja2.Template(mail_template)
    mail_body = rtemplate.render(action_url=target_url, support_url="mailto:feedback@imageimprov.com")

    mailgun_APIkey = 'key-6896c65db1a821c6e15ae34ae2ad94e9'  # shh! this is a secret
#    mailgun_SMTPpwd = 'e2b0c198a98ebf1f1a338bb4046352a1'
    mailgun_baseURL = 'https://api.mailgun.net/v3/api.imageimprov.com/messages'

    res = requests.post(mailgun_baseURL,
                        auth=("api", mailgun_APIkey),
                        data={"from": "Forgot Password <noreply@imageimprov.com>",
                              "to": emailaddress,
                              "subject": "Password reset",
                              "html": mail_body})
    '''
        200 - Everything work as expected
        400 - Bad Request - often missing required parameter
        401 - Unauthorized - No valid API key provided
        402 - Request failed - parameters were valid but request failed
        404 - Not found - requested item doesn't exist
        500, 502, 503, 504 - Server Errors - something wrong on Mailgun's end
    '''
    return res.status_code

def send_reset_password_notification_email(emailaddress) -> int:
    """
    Send a link to the user where they can reset their password. The token
    ensures what account is being reset.
    :param emailaddress:
    :param csrf:
    :return:
    """
    mail_template = read_template("email/password_changed.html")

    rtemplate = jinja2.Template(mail_template)
    mail_body = rtemplate.render(action_url=target_url, support_url="mailto:feedback@imageimprov.com")

    mailgun_APIkey = 'key-6896c65db1a821c6e15ae34ae2ad94e9'  # shh! this is a secret
#    mailgun_SMTPpwd = 'e2b0c198a98ebf1f1a338bb4046352a1'
    mailgun_baseURL = 'https://api.mailgun.net/v3/api.imageimprov.com/messages'
    mail_body = "You're password has been changed!"

    res = requests.post(mailgun_baseURL,
                        auth=("api", mailgun_APIkey),
                        data={"from": "Password Change <noreply@imageimprov.com>",
                              "to": emailaddress,
                              "subject": "Password Change notification",
                              "html": mail_body})
    '''
        200 - Everything work as expected
        400 - Bad Request - often missing required parameter
        401 - Unauthorized - No valid API key provided
        402 - Request failed - parameters were valid but request failed
        404 - Not found - requested item doesn't exist
        500, 502, 503, 504 - Server Errors - something wrong on Mailgun's end
    '''
    return res.status_code
