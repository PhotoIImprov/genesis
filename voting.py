from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
from dbsetup           import Session, Base, engine, metadata
import iiFile
import category

if __name__ == '__main__':
    if __name__ == '__main__':
        class Ballot(Base):
            __tablename__ = 'ballot'

            id           = Column(Integer, primary_key=True, autoincrement=True)
            category_id  = Column(Integer, ForeignKey("category.id"), nullable=False)
            user_id      = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)

            # all ballots at least 2 x 2
            file_id_1    = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)
            file_id_2    = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)
            file_id_3    = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)
            file_id_4    = Column(Integer, ForeignKey("iiFile.id"),  nullable=False)

            # some ballots may be 3 x 3 , so need 5 extra spots
            file_id_5    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)
            file_id_6    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)
            file_id_7    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)
            file_id_8    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)
            file_id_9    = Column(Integer, ForeignKey("iiFile.id"),  nullable=True)

            created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
            last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

            # ======================================================================================================

        # What is a Ballot?
        # A ballot is a group of images (probably 2 x 2 or 3 x 3 arrangement) that a user will
        # rank according to how well they feel the images relate to the current "category"
        # Users will have the opportunity to vote on multiple ballots, and each ballot entry
        # will be voted on by multiple users.
        #
        # A ballot is construction by choosing 4-9 randomly selected images associated with the
        # specified category
        #
        # A user should never see the *same* ballot twice, but entries on the ballot could be
        # almost entirely the same, particularly as the set of remaining entries is narrowed
        #

