from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, String
from dbsetup import Base
from logsetup import logger

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
    def get_url(session, id: int) -> str:
        bu = session.query(BaseURL).get(id)
        if bu is not None:
            return bu.url

        # user doesn't have anything special mapped for them,
        # so return the default URL
        return default_url()
