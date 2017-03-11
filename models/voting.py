from sqlalchemy        import Column, Integer, DateTime, text, ForeignKey
from sqlalchemy.orm import relationship, exc
import errno
from dbsetup           import Base, Session
from models import photo
import sys
import json
import base64
from flask import jsonify

_NUM_BALLOT_ENTRIES = 4

class Ballot(Base):
    __tablename__ = 'ballot'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_ballot_category_id"), nullable=False, index=True)
    user_id      = Column(Integer, ForeignKey("userlogin.id", name="fk_ballot_user_id"),  nullable=False, index=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    _ballotentries = relationship("BallotEntry", backref="ballot")
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
        count = 4 # number of photos in a ballot
        plist = Ballot.create_ballot_list(session, uid, cid, count)
        if plist is None:
            return None

        b = Ballot(cid, uid)
        # now create the ballot entries and attach to the ballot
        for p in plist:
            be = BallotEntry(p.user_id, p.category_id, p.id)
            be.set_photo(p)            # **** THIS IS GETTING OVERWRITTEN BY THE COMMIT???****
            b.add_ballotentry(be)

        # okay we have created ballot entries for our select photos
        # time to write it all out
        Ballot.write_ballot(session,b)

        # =========================================================
        # ==== we need to "reset" the photo information to the ====
        # ==== to the ballotentry, it's getting "lost" during  ====
        # ==== commit ???                                      ====
        # =========================================================
        for p in plist:
            for be in b._ballotentries:
                if be.photo_id == p.id:
                    be.set_photo(p)
                    break

        return b

    def to_json(self):

        ballots = []
        for be in self._ballotentries:
            ballots.append(be.to_json())

        return ballots

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
        .filter(BallotEntry.ballot_id == None, photo.Photo.user_id != uid).limit(count)

        p = q.all()
        return p

    # create_ballot_list()
    # ======================
    # we will read 'count' photos from the database
    # that don't belong to this user. We loop through
    # times voted on for our first 3 passes
    #
    # if we can't get 'count' photos, then we are done
    # Round #1...
    @staticmethod
    def create_ballot_list(session, uid, cid, count):
        if uid is None or cid is None or count is None:
            raise BaseException(errno.EINVAL)

        # we need "count"
        photos_for_ballot = []
        photos_for_ballot = Ballot.read_photos_not_balloted(session, uid, cid, count)

        for idx in range(1,3):
            if len(photos_for_ballot) >= count:
                return photos_for_ballot

            remaining_photos_needed = count - len(photos_for_ballot)
            # need more photos to construct the ballot
            q = session.query(photo.Photo)\
            .outerjoin(BallotEntry)\
            .filter(BallotEntry.ballot_id == idx, BallotEntry.user_id != uid).limit(remaining_photos_needed)
            p = q.all()
            if p is not None:
                photos_for_ballot.extend(p)

        return photos_for_ballot

    @staticmethod
    def tabulate_votes(session, uid, ballots):
        if uid is None or ballots is None:
            raise BaseException(errno.EINVAL)
        if len(ballots) < _NUM_BALLOT_ENTRIES:
            raise BaseException(errno.EINVAL)

        # okay we have everything we need, the category_id can be determined from the
        # ballot entry
        for ballotentry in ballots:
            likes = False
            if 'like' in ballotentry.keys():
                likes = True
            BallotEntry.tabulate_vote(session,  ballotentry['bid'], ballotentry['vote'], likes)

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

    photo = None
    _b64image = None
    _binary_image = None
    def __init__(self, uid, cid, pid):
        self.category_id = cid
        self.user_id = uid
        self.photo_id = pid
        self.vote = 0
        self.like = 0
        self.photo = None
        self._b64image = None
        self._binary_image = None
        return

    def set_photo(self, p):
        self.photo = p
        return

    def get_photo(self):
        if self.photo is None:
            try:
                self.photo = photo.Photo.read_photo_by_index(Session(), self.photo_id)
            except exc.NoResultFound:   # shouldn't happen except in testing with nested sessions
                return None

        return self.photo

    def to_json(self):

        if self.photo is None:
            return None

        self._binary_image = self.photo.read_thumbnail_image()
        if self._binary_image is None:
            return None

        self._b64image = base64.standard_b64encode(self._binary_image)
        if self._b64image is None:
            return None

        d = dict({'bid':self.id, 'image':self._b64image.decode('utf-8')})
        return d

    @staticmethod
    def find_ballotentries(session, bid, cid, uid):
        q = session.query(BallotEntry).filter_by(user_id = uid, category_id = cid, ballot_id = bid)
        be = q.all()
        return be

    def add_vote(self, vote):
        self.vote = self.vote + vote
        return
    def increment_like(self, l):
        if l == True:
            self.like = self.like + 1
        return

    @staticmethod
    def tabulate_vote(session, bid, vote, like):
        if bid is None:
            raise BaseException(errno.EINVAL)

        # okay, write this vote out to the ballot entry

        q = session.query(BallotEntry).filter_by(id = bid)
        be = q.one()
        if be is None:
            raise BaseException(errno.EADDRNOTAVAIL)

        be.add_vote(vote)
        be.increment_like(like)

        q = session.query(photo.Photo).filter_by(id = be.photo_id)
        p = q.one()
        if p is None:
            raise BaseException(errno.EADDRNOTAVAIL)

        p.increment_vote_count()

        session.commit()
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
            e = sys.exc_info()[0]
            # what happened here?
            raise

        return

#============================================= J S O N  D T O =============================================
class jBallot(json.JSONEncoder):
    jBallotEntries = []

    def __init__(self, b):
        # we have a ballot, distill it's essence
        be_list = []
        be_list = b.get_ballotentries()
        for be in be_list:
            jb = jBallotEntries(be)
            self.jBallotEntries.append(jb)
        return

    def default(self, o):
        json_str = "put json here"
        return json_str

class jBallotEntries(json.JSONEncoder):
    bid = 0
    image = None
    _binary_image = None

    def __init__(self,be):
        self.bid = be.id
        p = be.get_photo()
        if p is not None:
            self._binary_image = p.read_thumbnail_image()

        return
