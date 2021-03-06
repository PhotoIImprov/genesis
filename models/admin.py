"""Administrative functions"""
from datetime import datetime, timedelta
from uuid import uuid4
import urllib.parse
from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, String, Boolean
import sqlalchemy.orm
import requests
import jinja2
from dbsetup import Base
import dbsetup
from logsetup import logger


class BaseURL(Base):
    """the mobile apps first request is to get a base-url that can be
    used for all subsequent API calls. This allows us to segregate
    traffic on a per-user basis. Thus we can roll out code to a subset
    of the userbase"""

    __tablename__ = 'baseurl'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(255), nullable=False, index=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True,
                          server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    @staticmethod
    def default_url() -> str:
        """just a simple default URL for our base URL"""
        return 'https://api.imageimprov.com/'

    @staticmethod
    def get_url(session: sqlalchemy.orm.session, user_id: int) -> str:
        """fetch a base url based on the user id. If there is no match
        then use the default"""
        base_url_by_user = session.query(BaseURL).get(user_id)
        if base_url_by_user is not None:
            return base_url_by_user.url

        # user doesn't have anything special mapped for them,
        # so return the default URL
        return BaseURL.default_url()


class CSRFevent(Base):
    """Allows us to pass a token to the user that can be used
    only once for something like a forgot password. We can also
    set expiration on these events.
    """
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
        """
        A random string of bytes that can be safely encoded in a URL
        :return:
        """
        csrf = str(uuid4()).upper().translate({ord(c): None for c in '-'})
        url_safe_csrf = urllib.parse.quote_plus(csrf)
        return url_safe_csrf

    @staticmethod
    def get_csrfevent(session, token: str):
        """for the specified token, see if there's an event
        registered and return it. We don't check expiration here"""
        query = session.query(CSRFevent).filter_by(csrf=token)
        event = query.one()
        return event

    def mark_used(self):
        """mark the event as used"""
        self.been_used = True

    def isvalid(self)-> bool:
        """
        we have a CSRFevent object from the database, is it still valid?

        :return:
        """
        if self.been_used or self.expiration_date < datetime.now():
            return False

        return True


class Emailer():
    """class responsible for all outgoing emails"""

    _send_email = None
    def __init__(self, **kwargs):
        self._uid = kwargs.get('uid', None)
        # dependency injection...
        self._send_email = kwargs.get('f_sendemail', self.send_email)

    def read_template(self, template_name: str) -> str:
        """
        read the named template in as string
        :param template_name:
        :return:
        """
        base_dir = dbsetup.template_dir(environment=None)
        fname = base_dir + '/' + template_name
        try:
            file_pointer = open(fname, 'r')
            template = file_pointer.read()
            file_pointer.close()
            return template
        except Exception as e:
            logger.exception(msg="problem opening template")
            raise

    def send_forgot_password_email(self, emailaddress: str, csrf: str) -> int:
        """
        Send a link to the user where they can reset their password. The token
        ensures what account is being reset.
        :param emailaddress:
        :param csrf:
        :return:
        """

        mail_template = self.read_template("email/reset_password.html")
        root_url = dbsetup.root_url(environment=None)
        target_url = root_url + "/en-US/user/resetpassword.html?token={0}".format(csrf)

        rtemplate = jinja2.Template(mail_template)
        mail_body = rtemplate.render(action_url=target_url,
                                     support_url="mailto:feedback@imageimprov.com")

        status_code = self._send_email(to_email=emailaddress,
                                       from_email="Forgot Password <noreply@imageimprov.com>",
                                       subject_email="Password reset",
                                       body_email=mail_body)
        return status_code

    def send_reset_password_notification_email(self, emailaddress) -> int:
        """
        Send a link to the user where they can reset their password. The token
        ensures what account is being reset.
        :param emailaddress:
        :param csrf:
        :return:
        """
        mail_template = self.read_template("email/password_changed.html")

        rtemplate = jinja2.Template(mail_template)
        mail_body = rtemplate.render(support_url="mailto:feedback@imageimprov.com")

        status_code = self._send_email(to_email=emailaddress,
                                       from_email="Password Change <noreply@imageimprov.com>",
                                       subject_email="Password Change notification",
                                       body_email=mail_body)
        return status_code

    #     mailgun_APIkey = 'key-6896c65db1a821c6e15ae34ae2ad94e9'  # shh! this is a secret
    # #    mailgun_SMTPpwd = 'e2b0c198a98ebf1f1a338bb4046352a1'
    #     mailgun_baseURL = 'https://api.mailgun.net/v3/api.imageimprov.com/messages'
    #     mail_body = "You're password has been changed!"
    #
    #     res = requests.post(mailgun_baseURL,
    #                         auth=("api", mailgun_APIkey),
    #                         data={"from": "Password Change <noreply@imageimprov.com>",
    #                               "to": emailaddress,
    #                               "subject": "Password Change notification",
    #                               "html": mail_body})
    #     """
    #         200 - Everything work as expected
    #         400 - Bad Request - often missing required parameter
    #         401 - Unauthorized - No valid API key provided
    #         402 - Request failed - parameters were valid but request failed
    #         404 - Not found - requested item doesn't exist
    #         500, 502, 503, 504 - Server Errors - something wrong on Mailgun's end
    #     """
    #     return res.status_code

    @staticmethod
    def send_email(to_email: str, from_email: str, subject_email: str, body_email: str) -> int:
        """
        Sends an email via an external emailing service
        :param to_email:
        :param from_email:
        :param subject_email:
        :param body_email:
        :return:
        """
        mailgun_api_key = 'key-6896c65db1a821c6e15ae34ae2ad94e9'  # shh! this is a secret
        #    mailgun_SMTPpwd = 'e2b0c198a98ebf1f1a338bb4046352a1'
        mailgun_base_url = 'https://api.mailgun.net/v3/api.imageimprov.com/messages'

        res = requests.post(mailgun_base_url,
                            auth=("api", mailgun_api_key),
                            data={"from": from_email,
                                  "to": to_email,
                                  "subject": subject_email,
                                  "html": body_email})
        #
        #    200 - Everything work as expected
        #    400 - Bad Request - often missing required parameter
        #    401 - Unauthorized - No valid API key provided
        #    402 - Request failed - parameters were valid but request failed
        #    404 - Not found - requested item doesn't exist
        #    500, 502, 503, 504 - Server Errors - something wrong on Mailgun's end
        #
        return res.status_code
