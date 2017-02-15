from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base, engine, metadata

class Category(Base):
    __tablename__ = 'category'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    start_date   = Column(DateTime, nullable=False)
    end_date     = Column(DateTime, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    # ======================================================================================================
