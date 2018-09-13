""" for language mapping"""
from sqlalchemy import Column, Integer, String, DateTime, text
from logsetup import logger
from dbsetup import Base

RESOURCE_MAP = None


class Resource(Base):
    """manages language mapping"""
    __tablename__ = 'resource'

    resource_id = Column(Integer,
                         primary_key=True, autoincrement=True)
    iso639_1 = Column(String(2),
                      primary_key=True) # language of resource, e.g. "EN" or "ES"
    resource_string = Column(String(500),
                             nullable=False) # language-specific string

    created_date = Column(DateTime,
                          server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime,
                          nullable=True,
                          server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, rid, language, resource_str):
        self.resource_string = resource_str
        self.resource_id = rid
        self.iso639_1 = language

    @staticmethod
    def load_resource_by_id(session, rid, lang):
        """get a specific resource (string) by id & language"""
        query = session.query(Resource).\
            filter_by(resource_id=rid, iso639_1=lang)
        resource = query.one_or_none()
        return resource

    @staticmethod
    def load_resources(session):
        """load resources. get it all (probably for caching)"""
        # let's read the entire table in
        global RESOURCE_MAP
        RESOURCE_MAP = session.query(Resource).all()

    @staticmethod
    def create_resource(rid: int, language: str, resource_str: str):
        """create a resource object, not written to db"""
        resource = Resource(rid, language, resource_str)
        return resource

    @staticmethod
    def write_resource(session, resource) -> None:
        """create a resource"""
        session.add(resource)
        session.flush()

    @staticmethod
    def find_resource_by_string(resource_string: str, lang: str, session):
        """returns a resource by name & language"""
        query = session.query(Resource).filter(Resource.resource_string == resource_string,
                                               Resource.iso639_1 == lang)
        resource = query.first()
        return resource

    @staticmethod
    def create_new_resource(session, lang: str, resource_str: str):
        """create a new resource"""
        try:
            resource = Resource(None, lang, resource_str)
            session.add(resource)
            session.commit()
            return resource
        except Exception as e:
            logger.exception(msg="error creating new resource")
            session.close()
            raise
