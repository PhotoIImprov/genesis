from sqlalchemy import Column, Integer, String, DateTime, text
from dbsetup import Base
from pymysql import OperationalError, IntegrityError
import sys
from sqlalchemy.sql.expression import insert, select
from sqlalchemy import func
from logsetup import logger
from sqlalchemy import func

resource_map = None

class Resource(Base):
    __tablename__ = 'resource'

    resource_id     = Column(Integer,     primary_key=True, autoincrement=True) # identifier used to find relevant resource
    iso639_1        = Column(String(2),   primary_key=True) # language of resource, e.g. "EN" or "ES"
    resource_string = Column(String(500), nullable=False)                   # language-specific string

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

# ======================================================================================================
    def __init__(self, rid, language, resource_str):
        self.resource_string = resource_str
        self.resource_id     = rid
        self.iso639_1        = language
        return

    @staticmethod
    def load_resource_by_id(session, rid, lang):
        q = session.query(Resource).filter_by(resource_id = rid, iso639_1 = lang)
        r = q.one_or_none()
        return r

    @staticmethod
    def load_resources(session):
        # let's read the entire table in
        resource_map = session.query(Resource).all()

    @staticmethod
    def create_resource(rid, language, resource_str):
        r = Resource(rid, language, resource_str)
        return r

    @staticmethod
    def write_resource(session, r):
        session.add(r)
        session.flush()

    @staticmethod
    def find_resource_by_string(resource_string: str, lang: str, session):
        q = session.query(Resource).filter(Resource.resource_string==resource_string, Resource.iso639_1==lang)
        r = q.first()
        return r

    @staticmethod
    def create_new_resource(session, lang: str, resource_str: str):
        try:
            r = Resource(None, lang, resource_str)
            session.add(r)
            session.commit()
            return r
        except Exception as e:
            logger.exception(msg="error creating new resource")
            session.close()

        return None

