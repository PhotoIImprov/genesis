from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base, engine, metadata
import errno
import datetime

class Category(Base):
    __tablename__ = 'category'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    resource_id  = Column(Integer, ForeignKey("resource.resource_id", name="fk_category_resource_id"), nullable=False)
    start_date   = Column(DateTime, nullable=False)
    end_date     = Column(DateTime, nullable=False)


    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    # ======================================================================================================

    def get_id(self):
        return self.id

    @staticmethod
    def write_category(session, c):
        session.add(c)
        session.commit()

        PhotoIndex.create_index(session, c.id)
        return

    @staticmethod
    def create_category(rid, sd, ed):
        c = Category()
        c.resource_id = rid
        c.start_date = sd
        c.end_date = ed

        return c

    @staticmethod
    def current_category(session, uid):
        if session is None or uid is None:
            raise BaseException(errno.EINVAL)

        current_datetime = datetime.datetime.utcnow()
        q = session.query(Category).filter(Category.start_date < current_datetime). \
                                    filter(Category.end_date > current_datetime)
        c = q.all()
        if c is None or len(c) == 0:
            return None

        return c[0]

class PhotoIndex(Base):
    __tablename__ = 'photoindex'
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_photoindex_category_id"), primary_key=True, nullable=False)
    idx          = Column(Integer, nullable=False, default=0)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    # ======================================================================================================

    def __init__(self, cid, ix):
        self.category_id = cid
        self.idx = ix
        return

    @staticmethod
    def create_index(session, cid):
        pi = PhotoIndex(cid, 1)
        session.add(pi)
        session.commit()
        return

    @staticmethod
    def read_index(session, cid):
        q = session.query(PhotoIndex).filter_by(category_id = cid)
        pi = q.first()
        return pi
