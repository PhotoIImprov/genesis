from sqlalchemy        import Column, Integer, DateTime, text, ForeignKey
from sqlalchemy.orm import relationship
import errno
from dbsetup           import Base
from models import photo


class Ballot(Base):
    __tablename__ = 'ballot'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_ballot_category_id"), nullable=False, index=True)
    user_id      = Column(Integer, ForeignKey("userlogin.id", name="fk_ballot_user_id"),  nullable=False, index=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    _ballotentries = relationship("BallotEntry", back_populates="ballot")
    # ======================================================================================================

    def __init__(self, cid, uid):
        self.category_id    = cid
        self.user_id        = uid
        return

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


    # find_ballot()
    # =============
    # return all ballots for this user for the current category
    # and all ballot entries for each ballot
    #
    @staticmethod
    def find_ballot(session, uid, cid):
        q = session.query(Ballot).filter_by(user_id = uid, category_id = cid)
        b = q.one()
        return b

    def get_ballotentries(self):
        return self._ballotentries

    def add_ballotentry(self, ballotentry):
        self._ballotentries.append(ballotentry)
        return

    @staticmethod
    def write_ballot(session, b):
        session.add(b)
        session.commit()

    @staticmethod
    def create_ballot(session, uid, cid):
        return None

    # read_photos_not_balloted()
    # ==========================
    # Retrieve a list of photos that are not on
    # any ballots
    @staticmethod
    def read_photos_not_balloted(session, uid, cid, count):
        if uid is None or cid is None or count is None:
            raise BaseException(errno.EINVAL)

        q = session.query(photo.Photo)\
        .outerjoin(BallotEntry)\
        .filter(BallotEntry.ballot_id == None).limit(count)

        p = q.all()
        return p
#    @staticmethod
#    def number_ballotentries(pid):


class BallotEntry(Base):
    __tablename__ = 'ballotentry'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    ballot_id    = Column(Integer, ForeignKey('ballot.id', name='fk_ballotentry_ballot_id'), nullable=False, index=True)
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_ballotentry_category_id"), nullable=False, index=True)
    user_id      = Column(Integer, ForeignKey("userlogin.id", name="fk_ballotentry_user_id"),  nullable=False, index=True)
    photo_id     = Column(Integer, ForeignKey("photo.id", name="fk_ballotentry_photo_id"), nullable=False, index=True)
    vote         = Column(Integer, nullable=True) # ranking in the ballot

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    ballot = relationship("Ballot", back_populates="_ballotentries")

    @staticmethod
    def find_ballotentries(session, bid, cid, uid):
        q = session.query(BallotEntry).filter_by(user_id = uid, category_id = cid, ballot_id = bid)
        be = q.all()
        return be
