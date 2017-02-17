from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base, engine, metadata

class Category(Base):
    __tablename__ = 'category'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    resource_id  = Column(Integer, ForeignKey("resource.resource_id"), nullable=False)
    start_date   = Column(DateTime, nullable=False)
    end_date     = Column(DateTime, nullable=False)


    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    # ======================================================================================================

    @staticmethod
    def write_category(session, c):
        session.add(c)
        session.commit()
        return

    @staticmethod
    def create_category(rid, sd, ed):
        c = Category()
        c.resource_id = rid
        c.start_date = sd
        c.end_date = ed
        return c

