from sqlalchemy        import Column, Integer, DateTime, text, ForeignKey
from sqlalchemy.orm import relationship
import errno
from dbsetup           import Base
from models import photo
import sys


_NUM_BALLOT_ENTRIES = 4

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

    @staticmethod
    def tabulate_votes(session, uid, ballots):
        if uid is None or ballots is None:
            raise BaseException(errno.EINVAL)
        if len(ballots) < _NUM_BALLOT_ENTRIES:
            raise BaseException(errno.EINVAL)

        # okay we have everything we need, the category_id can be determined from the
        # ballot entry
        for ballotentry in ballots:
            BallotEntry.tabulate_vote(session,  ballotentry.bid, ballotentry.vote, ballotentry.like)

        session.commit()
        return

class BallotEntry(Base):
    __tablename__ = 'ballotentry'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    ballot_id    = Column(Integer, ForeignKey('ballot.id', name='fk_ballotentry_ballot_id'), nullable=False, index=True)
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_ballotentry_category_id"), nullable=False, index=True)
    user_id      = Column(Integer, ForeignKey("userlogin.id", name="fk_ballotentry_user_id"),  nullable=False, index=True)
    photo_id     = Column(Integer, ForeignKey("photo.id", name="fk_ballotentry_photo_id"), nullable=False, index=True)
    vote         = Column(Integer, nullable=True) # ranking in the ballot
    like         = Column(Integer, nullable=False, default=0) # if this photo was "liked"

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    ballot = relationship("Ballot", back_populates="_ballotentries")

    @staticmethod
    def find_ballotentries(session, bid, cid, uid):
        q = session.query(BallotEntry).filter_by(user_id = uid, category_id = cid, ballot_id = bid)
        be = q.all()
        return be

    def add_vote(self, vote):
        self.vote = self.vote + vote
        return
    def increment_like(self, l):
        if l == 1:
            self.like = self.like + 1
        return

    @staticmethod
    def tabulate_vote(session, bid, vote, like):
        if bid is None:
            raise BaseException(errno.EINVAL)

        # okay, write this vote out to the ballot entry

        q = session.query(BallotEntry).filterby(ballot_id = bid)
        be = q.one()
        if be is None:
            raise BaseException(errno.EADDRNOTAVAIL)

        be.add_vote(vote)
        be.increment_like(like)

        q = session.query(photo.Photo).filterby(be.photo_id)
        p = q.one()
        if p is None:
            raise BaseException(errno.EADDRNOTAVAIL)

        p.increment_vote_count()

        session.update(be)
        session.update(p)
        return

class LeaderBoard(Base):
    __tablename__ = 'leaderboard'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_leaderboard_category_id"), nullable=False, index=True, primary_key=True)
    user_id      = Column(Integer, ForeignKey("userlogin.id", name="fk_leaderboard_user_id"),  nullable=False, index=True)
    score        = Column(Integer, nullable=True) # current score
    votes        = Column(Integer, nullable=True) # ranking in the ballot
    likes        = Column(Integer, nullable=False, default=0) # how many times their photo has been liked

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    @staticmethod
    def leaderboard_list(session, cid):
        q = session.query(LeaderBoard).filter_by(category_id = cid)
        leaders = q.all()
        return leaders

    @staticmethod
    def update_leaderboard(session, uid, cid, vote, likes, score):
        # okay need to check if leaderboard needs an update
        if uid is None or cid is None:
            raise BaseException(errno.EINVAL)

        try:
            results = session.execute('CALL sp_updateleaderboard(:uid,:cid,:in_likes,:in_vote,:in_score);', {"uid": uid, "cid": cid, "in_likes":likes, "in_vote":vote, "in_score":score})
            session.commit()
        except:
            e = sys.exec_info()[0]
            # what happened here?
            raise

        return
