from sqlalchemy        import Column, Integer, DateTime, text, ForeignKey, String, exc
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session
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
from random import randint, shuffle


# configuration values we can move to a better place
_NUM_BALLOT_ENTRIES = 4
_NUM_SECTONS_ROUND2 = 4
_ROUND1_SCORING     = {0:[3,1,0,0]}
_ROUND2_SCORING     = {0:[7,5,3,1], 1:[6,4,2,2], 2:[5,3,1,1], 3:[4,2,0,1]}
_ROUND1_TIMESVOTED  = 3
_ROUND2_TIMESVOTED  = 3

class Ballot(Base):
    __tablename__ = 'ballot'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    category_id  = Column(Integer, ForeignKey("category.id", name="fk_ballot_category_id"), nullable=False, index=True)
    user_id      = Column(Integer, ForeignKey("anonuser.id", name="fk_ballot_user_id"),  nullable=False, index=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    _ballotentries = relationship("BallotEntry", backref="ballot", lazy='joined')
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

    def read_photos_for_ballots(self, session):
        for be in self._ballotentries:
            be._photo = session.query(photo.Photo).get(be.photo_id)

    def get_ballotentries(self):
        return self._ballotentries

    def append_ballotentry(self, ballotentry):
        self._ballotentries.append(ballotentry)
        return

    def to_json(self):

        ballots = []
        for be in self._ballotentries:
            ballots.append(be.to_json())

        return ballots

    @staticmethod
    def num_voters_by_category(session, cid):
        q = session.query(Ballot.user_id).distinct().filter(Ballot.category_id == cid)
        n = q.count()
        return n

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

    _photo = None # relationship("photo.Photo", backref="ballotentry", uselist=False, lazy='joined')

    _b64image = None
    _binary_image = None

    def __init__(self, **kwargs):
        self.id = kwargs.get('ballotentry_id', None)
        self.vote = kwargs.get('vote', 0)
        self.like = kwargs.get('like', 0)
        self.user_id = kwargs.get('user_id', None)
        self.photo_id = kwargs.get('photo_id', None)
        self.category_id = kwargs.get('category_id', None)
        self._photo = None
        self._b64image = None
        self._binary_image = None

    def to_json(self):
        if self._photo is None:
            return None
        self._binary_image = self._photo.read_thumbnail_image()
        if self._binary_image is None:
            return None

        self._b64image = base64.standard_b64encode(self._binary_image)
        if self._b64image is None:
            return None

        orientation = self._photo.get_orientation()

        d = dict({'bid':self.id, 'image':self._b64image.decode('utf-8'), 'orientation': orientation})
        return d


class VotingRound(Base):
    __tablename__ = 'voting_round'
    photo_id = Column(Integer, ForeignKey("photo.id", name="fk_votinground_photo_id"), nullable=False, primary_key=True)
    section = Column(Integer, nullable=False)
    times_voted = Column(Integer, nullable=True, default=0)

    # ======================================================================================================
    def __init__(self, **kwargs):
        self.photo_id = kwargs.get('photo_id', None)


class BallotManager:
    '''
    Ballot Manager
    This class is responsible to creating our voting ballots
    '''

    _ballot = None

    def tabulate_votes(self, session, uid, json_ballots):
        # we have a list of ballots, we need to determine the scoring.
        # we'll need category information:
        # category.round - to determine what score table to use
        # votinground.section - further define for round #2 what scoring to use

        # It's possible the ballotentries are from different sections, we'll
        # score based on the first ballotentry
        bid = json_ballots[0]['bid']
        be = session.query(BallotEntry).get(bid)
        vr = session.query(VotingRound).get(be.photo_id)
        section = vr.section
        cat = session.query(category.Category).get(be.category_id)
        round = cat.round

        for j_be in json_ballots:
            bid = j_be['bid']
            if 'like' in j_be.keys():
                like = 1
            else:
                like = 0

            be = session.query(BallotEntry).get(bid)
            be.like = like
            be.vote = j_be['vote']
            score = self.calculate_score(j_be['vote'], round, section)
            p = session.query(photo.Photo).get(be.photo_id)
            p.score += score
            p.times_voted += 1

            tm = TallyMan()
            tm.update_leaderboard(session, uid, cat.id, p)

        return cat.id

    def calculate_score(self, vote, round, section):
        if round == 0:
            score = _ROUND1_SCORING[0][vote-1]
        else:
            score = _ROUND2_SCORING[section][vote-1]

        return score

    def create_ballot(self, session, uid, cid):
        '''
        Returns a ballot list containing the photos to be voted on.
        
        :param session: 
        :param uid: 
        :param cid: 
        :return: dictionary: error:<error string>
                             arg: ballots()
        '''
        # determine what round of voting
        d = category.Category.read_category_by_id(session, cid)
        c = d['arg']

        if c is None:
            return d

        # Voting Rounds are stored in the category, 0= Round #1, 1= Round #2
        if c.round == 0:
            return self.create_ballot_ROUND1(session, uid, cid)

        return self.create_ballot_ROUND2(session,uid, cid)

    def create_ballot_ROUND1(self, session, uid, cid):
        d = self.create_ballot_list_ROUND1(session, uid, cid, _NUM_BALLOT_ENTRIES)
        plist = d['arg']
        if plist is None:
            return d

        return self.add_photos_to_ballot(session, uid, cid, plist)

    def create_ballot_ROUND2(self, session,uid, cid):
        plist = self.create_ballot_list_ROUND2(session, uid, cid, _NUM_BALLOT_ENTRIES)
        if plist is None:
            return {'error': 'no ballot', 'arg': None}

        # update VotingRound to track photo ballot usage
        self.update_votinground(session, plist)

        return self.add_photos_to_ballot(session, uid, cid, plist)

    def update_votinground(self, session, plist):
        for p in plist:
            session.query(VotingRound).filter(VotingRound.photo_id == p.id).update({"times_voted": VotingRound.times_voted + 1})
        return

    def add_photos_to_ballot(self, session, uid, cid, plist):

        self._ballot = Ballot(cid, uid)
        session.add(self._ballot)
        mysession = Session.object_session(self._ballot) # debugging to see what session it's bound to

        # now create the ballot entries and attach to the ballot
        for p in plist:
            be = BallotEntry(user_id=p.user_id, category_id=cid, photo_id=p.id)
            self._ballot.append_ballotentry(be)
            session.add(be)

#        except exc.IntegrityError as e:
#            if 'fk_ballot_user_id' in e.args[0] or 'fk_ballot_category_id' in e.args[0]:
#                return {'error':error.iiServerErrors.INVALID_USER, 'arg':None} # someone passed us an improper user_id
#            raise # tell someone up what the problem is...

        return {'error':None, 'arg':self._ballot}

    def create_ballot_list_ROUND2(self, session, uid, cid, num_ballots):
        if session is None or uid is None or cid is None:
            return None

        # *****************************
        # **** CONFIGURATION ITEMS ****
        num_sections = _NUM_SECTONS_ROUND2    # the "stratification" of the photos that received votes or likes
        max_votes = _ROUND2_TIMESVOTED        # The max # of votes we need to pick a winner
        # ****************************

        # create an array of our sections
        sl = []
        for idx in range(num_sections):
            sl.append(idx)

        bl = []
        for tv in range(max_votes):
            shuffle(sl)  # randomize the section list
            for idx in range(num_sections):
                q = session.query(photo.Photo).filter(photo.Photo.user_id != uid). \
                    filter(photo.Photo.category_id == cid).\
                    join(VotingRound, VotingRound.photo_id == photo.Photo.id) . \
                    filter(VotingRound.section == sl[idx]). \
                    filter(VotingRound.times_voted == tv).limit(num_ballots)
                p = q.all()
                if len(p) == num_ballots:
                    return p

                bl.append(p) # accumulate ballots we've picked, can save us time later

        # see if we encountered 4 in our journey
        if len(pl) >= num_ballots:
            p = pl[num_ballots:] # we'll use these, only return 4
            return p

        # we tried everything, let's just grab some photos from any section (HOW TO RANDOMIZE THIS??)
        q = session.query(photo.Photo).filter(photo.Photo.user_id != uid). \
            filter(photo.Photo.category_id == cid). \
            join(VotingRound, VotingRound.photo_id == photo.Photo.id). \
            filter(VotingRound.times_voted == tv).limit(num_ballots)
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
    def create_ballot_list_ROUND1(self, session, uid, cid, count):
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
        photos_for_ballot = self.read_photos_not_balloted(session, uid, cid, count)

        if len(photos_for_ballot) >= count:
            return {'error': None, 'arg':photos_for_ballot}

        for num_votes in range(0,4):
            remaining_photos_needed = count - len(photos_for_ballot)
            if remaining_photos_needed == 0:
                break;
            # need more photos to construct the ballot
            p = self.read_photos_by_votes(session, uid, cid, num_votes, remaining_photos_needed)
            if p is not None:
                photos_for_ballot.extend(p)

        return {'error': None, 'arg':photos_for_ballot}

    # read_photos_not_balloted()
    # ==========================
    # Retrieve a list of photos that are not on
    # any ballots
    def read_photos_not_balloted(self, session, uid, cid, count):
        if uid is None or cid is None or count is None:
            raise BaseException(errno.EINVAL)

        q = session.query(photo.Photo).filter(photo.Photo.category_id == cid).\
            filter(photo.Photo.user_id != uid).\
            filter(~exists().where(BallotEntry.photo_id == photo.Photo.id)).limit(count)

        p = q.all()
        return p

    def read_photos_by_votes(self, session, uid, cid, num_votes, count):
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
        session.add(c)

        if new_state == category.CategoryState.VOTING.value:
            self.setup_voting(session, c)

        return {'error': None, 'arg': c}

    def leaderboard_name(self, cid):
        return "round_1_category{}".format(cid)

    def update_leaderboard(self, session, uid, cid, p):
        # we have a User/Photo/Vote
        lb = self.get_leaderboard_by_category_id(session, cid)
        if lb is not None:
            lb.rank_member(uid, p.score, p.id)

    def get_leaderboard_by_category_id(self, session, cid):
        rd = ServerList().get_redis_server(session)
        lb = Leaderboard(self.leaderboard_name(cid), host=rd['ip'], port=rd['port'], page_size=10)
        return lb

    def create_displayname(self, session, uid):
        u = usermgr.User.find_user_by_id(session, uid)
        if u is None:
            return "anonymous{}".format(uid)

        if u.screenname is not None:
            return u.screenname

        # if forced to use the email, don't return the domain
        ep = u.emailaddress.split('@')
        return ep[0]

    def read_thumbnail(self, session, pid):
        p = session.query(photo.Photo).get(pid)
        if p is None:
            return ''
        bimg = p.read_thumbnail_image()
        if bimg is None:
            return ''
        b64 = base64.standard_b64encode(bimg)
        if b64 is None:
            return ''
        b64_utf8 = b64.decode('utf-8')
        return b64_utf8

    def create_leaderboard(self, session, uid, cid):
        if cid is None:
            return None

        # okay lets get the leader board!
        lb = self.get_leaderboard_by_category_id(session, cid)
        if lb is None:
            return None

        my_rank = lb.rank_for(uid)

        dl = lb.leaders(1, page_size=10, with_member_data=True)   # 1st page is top 25
        lb_list = []
        for d in dl:
            lb_uid = int(str(d['member'], 'utf-8'))         # anonuser.id / userlogin.id
            lb_pid = int(str(d['member_data'], 'utf-8'))    # photo.id
            lb_score = d['score']
            lb_rank = d['rank']
            lb_name = self.create_displayname(session, lb_uid)

            b64_utf8 = self.read_thumbnail(session, lb_pid) # thumbnail image as utf-8 base64

            if lb_uid == uid:
                lb_list.append({'username': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'you':True, 'image' : b64_utf8})
            else:
                if usermgr.Friend.is_friend(session, uid, lb_uid):
                    lb_list.append({'username': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'isfriend':True, 'image' : b64_utf8})
                else:
                    lb_list.append({'username': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'image' : b64_utf8})

        return lb_list