from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base, engine, metadata
import iiFile
import category

class Ballot(Base):
    __tablename__ = 'ballot'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    category_id  = Column(Integer, ForeignKey("category.id"), nullable=False)
    user_id      = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)
    file_id_1    = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)
    file_id_2    = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)
    file_id_3    = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)
    file_id_4    = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)
    file_id_5    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)
    file_id_6    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)
    file_id_7    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)
    file_id_8    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)
    file_id_9    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    # ======================================================================================================
