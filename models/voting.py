from sqlalchemy        import Column, Integer, DateTime, text, ForeignKey, String, exc
from sqlalchemy.orm import relationship
from sqlalchemy import exists, and_
import errno
from dbsetup           import Base, Session
from models import photo, category, usermgr
import sys
import json
import base64
from flask import jsonify
from leaderboard.leaderboard import Leaderboard
from models import error


_NUM_BALLOT_ENTRIES = 4

class Ballot(Base):
    __tablename__ = 'ballot'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_ballot_category_id"), nullable=False, index=True)
    user_id      = Column(Integer, ForeignKey("anonuser.id", name="fk_ballot_user_id"),  nullable=False, index=True)

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
#    @staticmethod
#    def find_ballot(session, uid, cid):
#        q = session.query(Ballot).filter_by(user_id = uid, category_id = cid)
#        b = q.one()
#        return b

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
        d = Ballot.create_ballot_list(session, uid, cid, count)
        plist = d['arg']
        if plist is None:
            return d

        b = Ballot(cid, uid)
        # now create the ballot entries and attach to the ballot
        for p in plist:
            be = BallotEntry(p.user_id, p.category_id, p.id)
            be.set_photo(p)            # **** THIS IS GETTING OVERWRITTEN BY THE COMMIT???****
            b.add_ballotentry(be)

        # okay we have created ballot entries for our select photos
        # time to write it all out
        try:
            Ballot.write_ballot(session,b)
        except exc.IntegrityError as e:
            if 'fk_ballot_user_id' in e.args[0] or 'fk_ballot_category_id' in e.args[0]:
                return {'error':error.iiServerErrors.INVALID_USER, 'arg':None} # someone passed us an improper user_id
            raise # tell someone up what teh problem is...

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

        return {'error':None, 'arg':b}

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

        q = session.query(photo.Photo).filter(photo.Photo.category_id == cid).\
            filter(photo.Photo.user_id != uid).\
            filter(~exists().where(BallotEntry.photo_id == photo.Photo.id)).limit(count)

        p = q.all()
        return p

    @staticmethod
    def read_photos_by_votes(session, uid, cid, num_votes, count):
        if uid is None or cid is None or count is None:
            raise BaseException(errno.EINVAL)

        # if ballotentry has been voted on, exclude photos the user has already seen
        if num_votes == 0:
            q = session.query(photo.Photo).filter(photo.Photo.category_id == cid).\
                filter(photo.Photo.times_voted == num_votes).\
                filter(photo.Photo.user_id != uid).limit(count)
        else:
            q = session.query(photo.Photo).filter(photo.Photo.category_id == cid).\
                join(BallotEntry, photo.Photo.id == BallotEntry.photo_id).\
                filter(photo.Photo.times_voted == num_votes).\
                filter(BallotEntry.user_id != uid).\
                filter(photo.Photo.user_id != uid).limit(count)

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

        # is this category open for voting?
        d = category.Category.read_category_by_id(session, cid)
        c = d['arg']
        if c is None:
            return d

        if c.state != category.CategoryState.VOTING.value:
            return {'error': error.iiServerErrors.NOTVOTING_CATEGORY, 'arg': None}

        # we need "count"
        photos_for_ballot = []
        photos_for_ballot = Ballot.read_photos_not_balloted(session, uid, cid, count)

        if len(photos_for_ballot) >= count:
            return {'error': None, 'arg':photos_for_ballot}

        for num_votes in range(0,4):
            remaining_photos_needed = count - len(photos_for_ballot)
            if remaining_photos_needed == 0:
                break;
            # need more photos to construct the ballot
            p = Ballot.read_photos_num_votes(session, uid, cid, num_votes, remaining_photos_needed)
            if p is not None:
                photos_for_ballot.extend(p)

        return {'error': None, 'arg':photos_for_ballot}

    @staticmethod
    def tabulate_votes(session, uid, ballots):
        if uid is None or ballots is None:
            raise BaseException(errno.EINVAL)

        cid = None
        # okay we have everything we need, the category_id can be determined from the
        # ballot entry
        for ballotentry in ballots:
            likes = False
            if 'like' in ballotentry.keys():
                likes = True
            be = BallotEntry.tabulate_vote(session,  ballotentry['bid'], ballotentry['vote'], likes)
            cid = be.category_id

        session.commit()
        return cid

class BallotEntry(Base):
    __tablename__ = 'ballotentry'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    ballot_id    = Column(Integer, ForeignKey('ballot.id', name='fk_ballotentry_ballot_id'), nullable=False, index=True)
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_ballotentry_category_id"), nullable=False, index=True)
    user_id      = Column(Integer, ForeignKey("anonuser.id", name="fk_ballotentry_user_id"),  nullable=False, index=True)
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

#    def get_photo(self):
#        if self.photo is None:
#            try:
#                self.photo = photo.Photo.read_photo_by_index(Session(), self.photo_id)
#            except exc.NoResultFound:   # shouldn't happen except in testing with nested sessions
#                return None
#
#        return self.photo

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

#    @staticmethod
#    def find_ballotentries(session, bid, cid, uid):
#        q = session.query(BallotEntry).filter_by(user_id = uid, category_id = cid, ballot_id = bid)
#        be = q.all()
#        return be

    def set_vote(self, vote):
        self.vote = vote

    def set_like(self, l):
        self.like = l

    @staticmethod
    def tabulate_vote(session, bid, vote, like):
        if bid is None:
            raise BaseException(errno.EINVAL)

        # okay, write this vote out to the ballot entry

        q = session.query(BallotEntry).filter_by(id = bid)
        be = q.one()
        if be is None:
            raise BaseException(errno.EADDRNOTAVAIL)

        # check the category, is voting still happening?
        if not category.Category.is_voting_by_id(session, be.category_id):
            raise BaseException(errno.EINVAL)

        be.set_vote(vote)
        be.set_like(like)

        tm = TallyMan()
        tm.tabulate_vote(session, be.user_id, be.category_id, be.photo_id, vote)

        session.commit() # make sure ballotentry is written out
        return be

class ServerList(Base):
    __tablename__ = 'serverlist'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(32), nullable=False, index=True)
    ipaddress = Column(String(16), nullable=False, index=False)
    hostname = Column(String(255), nullable=False, index=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True,
                          server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    # ======================================================================================================

    def get_redis_server(self, session):
        # read the database and find a redis server for us to use
        q = session.query(ServerList).filter_by(type = 'Redis').order_by(ServerList.created_date.desc())
        rs = q.first()
        ipaddress = '127.0.0.1'
        port = 6379
        if rs is not None:
            ipaddress = rs.ipaddress

        d = {'ip':ipaddress, 'port':port}
        return d

# this is the class that will orchestrate our voting. So it's job is to:
#
#  - transition categories to appropriate states
#  - set up leaderboard table for round #1
#  - create queues for round #2
#  - close voting and summarize votes
#  - any other ancillary needs of voting
#
class TallyMan():

    # switch our category over to Voting and perform any housekeeping that is required
    def setup_voting(self, session, c):

        if c is None or not c.is_voting():
            return None # this is an error!

        # before we switch on voting, create the leaderboard
        sl = ServerList()
        d = sl.get_redis_server(session)

        redis_host = d['ip']
        redis_port = d['port']
        lb_name = self.leaderboard_name(c.get_id())
        lb = Leaderboard(lb_name, host=redis_host, port=redis_port, page_size=10)
        if lb is None:
            return None

        # start with a clean leaderboard
        lb.delete_leaderboard()

    def change_category_state(self, session, cid, new_state):

        d = category.Category.read_category_by_id(session, cid)

        if d['error'] is not None:
            session.close()
            return d

        # we have a legit category, see if the state needs to change
        c = d['arg']
        if c.state == new_state:
            return {'error':error.iiServerErrors.NO_STATE_CHANGE, 'arg':None}

        c.state = new_state
        session.commit()

        if new_state == category.CategoryState.VOTING.value:
            self.setup_voting(session, c)

        return {'error': None, 'arg': c}

    def leaderboard_name(self, cid):
        return "round_1_category{}".format(cid)

    def calculate_score(self, vote):
        # vote is  ranking: 1st or 2nd
        if vote == 1:
            return 7
        if vote == 2:
            return 3
        return 0

    def tabulate_vote(self, session, uid, cid, pid, vote):

        vote_score = self.calculate_score(vote)
        if vote_score == 0:
            return

        # okay the photo's score is going to change
        q = session.query(photo.Photo).filter_by(id = pid)
        p = q.one()
        if p is None:
            raise BaseException(errno.EADDRNOTAVAIL)

        p.increment_vote_count()
        score = p.update_score(vote_score)
        session.commit()

        # we have a User/Photo/Vote
        lb = self.get_leaderboard_by_category_id(cid)
        if lb is not None:
            lb.rank_member(uid, score, p.id)
        return

    def get_leaderboard_by_category_id(self, cid):
        return Leaderboard(self.leaderboard_name(cid))

    def create_displayname(self, session, uid):
        u = usermgr.User.find_user_by_id(session, uid)
        if u is None:
            return "anonymous{}".format(uid)

        if u.screenname is not None:
            return u.screenname

        # if forced to use the email, don't return the domain
        ep = u.emailaddress.split('@')
        return ep[0]

    def create_leaderboard(self, session, uid, cid):
        if cid is None:
            return None

        # okay lets get the leader board!
        lb = self.get_leaderboard_by_category_id(cid)
        if lb is None:
            return None

        my_rank = lb.rank_for(uid)

        dl = lb.leaders(1, page_size=10, with_member_data=True)   # 1st page is top 25
        lb_list = []
        in_list = False
        for d in dl:
            lb_uid = int(str(d['member'], 'utf-8'))
            lb_pid = int(str(d['member_data'], 'utf-8'))
            lb_score = d['score']
            lb_rank = d['rank']
            lb_name = self.create_displayname(session, lb_uid)

            if lb_uid == uid:
                in_list = True
                lb_list.append({'name': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'you':True})
            else:
                if usermgr.Friend.is_friend(session, uid, lb_uid):
                    lb_list.append({'name': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'isfriend':True})
                else:
                    lb_list.append({'name': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid})

        # see if we need to include ourselves in the list
        if my_rank is not None and not in_list:
            my_score = lb.rank_for(uid)
            lb_list.append({'name': self.create_displayname(session, uid), 'score':my_score,'rank':my_rank, 'you':True})

        return lb_list