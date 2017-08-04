import errno
from datetime import timedelta, datetime
from enum import Enum

from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, String

import dbsetup
from cache.iiMemoize import memoize_with_expiry, _memoize_cache
from dbsetup import Base
from logsetup import logger
from models import resources
from models import usermgr
from cache.ExpiryCache import _expiry_cache

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
        return 'https://api.imageimprov.com'

    @staticmethod
    def get_url(session, uid: int) -> str:
        bu = session.query(BaseURL).get(uid)
        if bu is not None:
            return bu.url

        # user doesn't have anything special mapped for them,
        # so return the default URL
        return default_url()
