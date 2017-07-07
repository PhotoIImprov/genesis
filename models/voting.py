from sqlalchemy        import Column, Integer, DateTime, text, ForeignKey, String, exc, func
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session
from sqlalchemy import exists, and_
import errno
from dbsetup           import Base, Session, Configuration
from models import photo, category, usermgr
import sys
import json
import base64
from flask import jsonify
from leaderboard.leaderboard import Leaderboard
from models import error
from random import randint, shuffle
import redis

from logsetup import logger

# configuration values we can move to a better place
_NUM_BALLOT_ENTRIES = 4
_NUM_SECTONS_ROUND2 = 4
_ROUND1_SCORING     = {0:[3,1,0,0]}
_ROUND2_SCORING     = {0:[7,5,3,1], 1:[6,4,2,2], 2:[5,3,1,1], 3:[4,2,0,1]}
_ROUND1_TIMESVOTED  = 3
_ROUND2_TIMESVOTED  = 3
_MAX_VOTING_ROUNDS  = 4

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

    def append_ballotentry(self, be):
        self._ballotentries.append(be)

    def read_photos_for_ballots(self, session):
        for be in self._ballotentries:
            be._photo = session.query(photo.Photo).get(be.photo_id)

    def append_tags_to_entires(self, c):
        if len(c._categorytags) == 0:
            return

        for be in self._ballotentries:
            be._tags = c._categorytags

    def to_log(self):
        """
        Dump out the list of ballot entries as a string for the log
        :return: 
        """
        str_ballots = 'category_id={}\n '.format(self.category_id)
        for be in self._ballotentries:
            str_ballots += 'bid:{0}, photo:{1}\n'.format(be.id, be.photo_id)

        return str_ballots

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
    offensive    = Column(Integer, nullable=False, default=0) # indicates user found the image objectionable

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    _photo = None # relationship("photo.Photo", backref="ballotentry", uselist=False, lazy='joined')

    _b64image = None
    _binary_image = None
    _tags = None

    def __init__(self, **kwargs):
        self.id = kwargs.get('ballotentry_id', None)
        self.vote = kwargs.get('vote', 0)
        self.like = kwargs.get('like', 0)
        self.offensive = kwargs.get('offensive', 0)
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
        self._b64image = base64.standard_b64encode(self._binary_image)

        orientation = self._photo.get_orientation()
        if orientation is None:
            orientation = 1

        if self._tags is None:
            d = dict({'bid': self.id, 'orientation': orientation, 'image': self._b64image.decode('utf-8')})
        else:
            d = dict({'bid':self.id, 'orientation': orientation, 'tags': self._tags.to_str(), 'image':self._b64image.decode('utf-8')})

        return d


class VotingRound(Base):
    __tablename__ = 'voting_round'
    photo_id = Column(Integer, ForeignKey("photo.id", name="fk_votinground_photo_id"), nullable=False, primary_key=True)
    section = Column(Integer, nullable=False)
    times_voted = Column(Integer, nullable=True, default=0)

    # ======================================================================================================
    def __init__(self, **kwargs):
        self.photo_id = kwargs.get('photo_id', None)


class BallotEntryTag(Base):
    __tablename__ = 'ballotentrytag'
    bid          = Column(Integer, ForeignKey('ballotentry.id', name='fk_ballotentrytag_bid'), primary_key=True)
    tags         = Column(String(1000), nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, **kwargs):
        self.bid = kwargs.get('bid', None)
        tag_list = kwargs.get('tags', None) # the tags dictionary
        self.tags = json.dumps(tag_list)



class BallotManager:
    '''
    Ballot Manager
    This class is responsible to creating our voting ballots
    '''

    _ballot = None

    def string_key_to_boolean(self, dict, keyname):
        '''
        if key is not present, return a '0'
        if key is any value other than '0', return '1'
        :param dict:
        :param keyname:
        :return: 0/1
        '''
        if keyname in dict.keys():
            str_val = dict[keyname]
            if str_val != '0':
                return 1
        return 0

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
        section = 0
        if vr is not None: # sections only matter for round 2
            section = vr.section

        c = session.query(category.Category).get(be.category_id)

        bel = []
        for j_be in json_ballots:
            bid = j_be['bid']
            like = self.string_key_to_boolean(j_be, 'like')
            offensive = self.string_key_to_boolean(j_be, 'offensive')

            # if there is an 'iitag' specified, then create a BallotEntryTag
            # record and save it
            try:
                if 'iitags' in j_be.keys():
                    tags = j_be['iitags']
                    be_tags = BallotEntryTag(bid=bid, tags=tags)
                    session.add(be_tags)
            except Exception as e:
                logger.exception(msg = "error while writing ballotentrytag")
                raise

            try:
                be = session.query(BallotEntry).get(bid)
                be.like = like
                be.offensive = offensive
                be.vote = j_be['vote']
                score = self.calculate_score(j_be['vote'], c.round, section)
                p = session.query(photo.Photo).get(be.photo_id)
                p.score += score
                p.times_voted += 1
                bel.append(be)
            except Exception as e:
                logger.exception(msg="error while updating photo with score")
                raise

            tm = TallyMan()
            try:
                tm.update_leaderboard(session, c, p) # leaderboard may not be defined yet!
            except:
                pass

        return bel  # this is for testing only, no one else cares!

    def calculate_score(self, vote, round, section):
        if round == 0:
            score = _ROUND1_SCORING[0][vote-1]
        else:
            score = _ROUND2_SCORING[section][vote-1]
        return score

    def create_ballot(self, session, uid, c, allow_upload=False):
        '''
        Returns a ballot list containing the photos to be voted on.
        
        :param session: 
        :param uid: 
        :param cid: 
        :return: dictionary: error:<error string>
                             arg: ballots()
        '''

        # Voting Rounds are stored in the category, 0= Round #1, 1= Round #2
        pl = self.create_ballot_list(session, uid, c)
        self.update_votinground(session, c, pl)
        return self.add_photos_to_ballot(session, uid, c, pl)

    def update_votinground(self, session, c, plist):
        if c.round == 0:
            return

        for p in plist:
            session.query(VotingRound).filter(VotingRound.photo_id == p.id).update({"times_voted": VotingRound.times_voted + 1})
        return

    def add_photos_to_ballot(self, session, uid, c, plist):

        self._ballot = Ballot(c.id, uid)
        session.add(self._ballot)

        # now create the ballot entries and attach to the ballot
        for p in plist:
            be = BallotEntry(user_id=p.user_id, category_id=c.id, photo_id=p.id)
            self._ballot.append_ballotentry(be)
            session.add(be)
        return self._ballot

    def read_photos_by_ballots_round2(self, session, uid, c, num_votes, count):

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
        shuffle(sl)  # randomize the section list
        oversize = count * 20
        for s in sl:
            q = session.query(photo.Photo).filter(photo.Photo.user_id != uid). \
                filter(photo.Photo.category_id == c.id).\
                filter(photo.Photo.active == 1). \
                join(VotingRound, VotingRound.photo_id == photo.Photo.id) . \
                filter(VotingRound.section == s). \
                filter(VotingRound.times_voted == num_votes).limit(oversize)
            pl = q.all()
            bl.extend(pl) # accumulate ballots we've picked, can save us time later
            # see if we encountered 4 in our journey
            if len(bl) >= count:
                return bl

        # we tried everything, let's just grab some photos from any section (HOW TO RANDOMIZE THIS??)
        if num_votes == _MAX_VOTING_ROUNDS:
            for s in sl:
                q = session.query(photo.Photo).filter(photo.Photo.user_id != uid). \
                    filter(photo.Photo.category_id == c.id). \
                    filter(photo.Photo.active == 1). \
                    join(VotingRound, VotingRound.photo_id == photo.Photo.id). \
                    filter(VotingRound.section == s).limit(oversize)
                pl = q.all()
                bl.extend(pl) # accumulate ballots we've picked, can save us time later
                if len(bl) >= count:
                    return bl
        return bl # return what we have

    # create_ballot_list()
    # ======================
    # we will read 'count' photos from the database
    # that don't belong to this user. We loop through
    # times voted on for our first 3 passes
    #
    # if we can't get 'count' photos, then we are done
    # Round #1...
    def create_ballot_list(self, session, uid, c, allow_upload=False):
        '''
        
        :param session: 
        :param uid: the user asking for the ballot (so we can exclude their photos) 
        :param c: category
        :return: a list of '_NUM_BALLOT_ENTRIES'. We ask for more than this,
                shuffle the result and trim the list lenght, so we get some randomness
        '''
        if c.state != category.CategoryState.VOTING.value and not allow_upload:
            raise Exception(errno.EINVAL, 'category not in VOTING state')

        # we need "count"
        count = _NUM_BALLOT_ENTRIES
        photos_for_ballot = []
        for num_votes in range(0,_MAX_VOTING_ROUNDS+1):
            if c.round == 0:
                pl = self.read_photos_by_ballots_round1(session, uid, c, num_votes, count)
            else:
                pl = self.read_photos_by_ballots_round2(session, uid, c, num_votes, count)

            if pl is not None:
                photos_for_ballot.extend(pl)
                if len(photos_for_ballot) >= count:
                    break

        return self.cleanup_list(photos_for_ballot, count) # remove dupes, shuffle list
#        return photos_for_ballot[:count]

    def cleanup_list(self, p4b, ballot_size):
        """
        We get a list of photos that are a straight pull from the
        database. We're going to shuffle it and not allow any
        duplicates based on 'thumb_hash'
        :param p4b:
        :param ballot_size:
        :return: list of ballots of 'ballot_size', randomized & scrubbed of duplicates (if possible)
        """

        shuffle(p4b)
        pretty_list = []
        for p in p4b:
            # we have a candidate photo, see if a copy is already in the list
            insert_p = True
            for dupe_check in pretty_list:
                if dupe_check._photometa.thumb_hash == p._photometa.thumb_hash:
                    insert_p = False
                    break
            if insert_p:
                pretty_list.append(p)
                if len(pretty_list) == ballot_size:
                    return pretty_list

        # worst cases just return a random list
        return p4b[:ballot_size]

    def read_photos_by_ballots_round1(self, session, uid, c, num_votes, count):
        '''
        read_photos_by_ballots_round1()
        read a list of photos to construct our return ballot. 

        :param session: 
        :param uid: user id that's voting, filter out photos that are their's 
        :param c: category
        :param num_votes: select photos with this # of votes 
        :param count: how many photos to fetch
        :return: list of Photo objects
        '''

        over_size = count * 20 # ask for a lot more so we can randomize a bit
        # if ballotentry has been voted on, exclude photos the user has already seen
        if num_votes == 0:
            q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
                filter(photo.Photo.user_id != uid). \
                filter(~exists().where(BallotEntry.photo_id == photo.Photo.id)).limit(over_size)
        else:
            if num_votes == _MAX_VOTING_ROUNDS:
                q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
                    join(BallotEntry, photo.Photo.id == BallotEntry.photo_id). \
                    filter(photo.Photo.user_id != uid). \
                    filter(photo.Photo.active == 1). \
                    group_by(photo.Photo.id).limit(over_size)
            else:
                q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id).\
                    join(BallotEntry, photo.Photo.id == BallotEntry.photo_id).\
                    filter(photo.Photo.user_id != uid).\
                    filter(photo.Photo.active == 1). \
                    group_by(photo.Photo.id).\
                    having(func.count(BallotEntry.photo_id) == num_votes).limit(over_size)

        pl = q.all()
        return pl

    def active_voting_categories(self, session, uid):
        '''
        Only return categories that have photos that can be voted on
        :param session: database connection
        :param uid: user id, incase there's a filter in the future
        :return: 
        '''
        q = session.query(category.Category).filter(category.Category.state == category.CategoryState.VOTING.value).\
            join(photo.Photo, photo.Photo.category_id == category.Category.id).\
            filter(photo.Photo.user_id != uid).\
            filter(photo.Photo.active == 1). \
            group_by(category.Category.id).having(func.count(photo.Photo.id) > 4)
        cl = q.all()

        # see if the user has uploaded to the current UPLOAD category, and if they have check to see
        # if there are enough photos include it in the vote-able category list
        q = session.query(category.Category).filter(category.Category.state == category.CategoryState.UPLOAD.value).\
            join(photo.Photo, photo.Photo.category_id == category.Category.id).\
            filter(photo.Photo.user_id == uid).\
            filter(photo.Photo.active == 1). \
            group_by(category.Category.id).having(func.count(photo.Photo.id) > 0)
        c_can_vote_on = q.all()

        if len(c_can_vote_on) > 0:
            q = session.query(category.Category).filter(category.Category.state == category.CategoryState.UPLOAD.value).\
                join(photo.Photo, photo.Photo.category_id == category.Category.id).\
                filter(photo.Photo.user_id != uid).\
                filter(photo.Photo.active == 1). \
                group_by(category.Category.id).having(func.count(photo.Photo.id) > Configuration.UPLOAD_CATEGORY_PICS)
            c_upload = q.all()

            # only items in c_can_vote_on and also in c_upload can be voted on
            # so "AND" the lists
            c_voteable = set(c_can_vote_on).intersection(c_upload)
            if len(c_voteable) > 0:
                set_list = list(c_voteable)
                cl.extend(set_list)

        return cl



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
    _redis_host = None
    _redis_port = None
    _redis_conn = None

    _orientation = None

    def leaderboard_exists(self, session, c):
        try:
            if self._redis_conn is None:
                sl = ServerList()
                d = sl.get_redis_server(session)
                self._redis_host = d['ip']
                self._redis_port = d['port']
                self._redis_conn = redis.Redis(host=self._redis_host, port=self._redis_port)

            lbname = self.leaderboard_name(c)
            return self._redis_conn.exists(lbname)
        except Exception as e:
            logger.exception(msg='error checking if leaderboard exists')
            raise

    def change_category_state(self, session, cid, new_state):
        c = category.Category.read_category_by_id(session, cid)
        if c.state == new_state:
            return {'error':error.iiServerErrors.NO_STATE_CHANGE, 'arg':None}

        c.state = new_state
        session.add(c)
        return {'error': None, 'arg': c}

    def leaderboard_name(self, c):
        try:
            str_lb = "leaderboard_category{0}".format(c.id)
        except Exception as e:
            logger.exception(msg='leaderboard_name(), error creating name')
            raise Exception(errno.EINVAL, 'cannot create leaderboard name')

        return str_lb

    def update_leaderboard(self, session, c, p, check_exist=True):
        '''
        update_leaderboard():
        Everytime a vote is cast, we'll update the leaderboard if it exists,
        otherwise we'll be counting on the background task to keep it up to date
        :param session: database connection
        :param c: - category
        :param p: - photo object, has score & id
        :param check_exist: =true if we should check if leaderboard exists
                            The updating of a leaderboard will create it if
                            it doesn't already exist. Leaderboard creation
                            is the sole province of the daemon that will
                            ensure leaderboards are created and populated
                            for non-voting categories in the event of a 
                            Redis failure.
        :return: 
        '''
        try:
            lb = self.get_leaderboard_by_category(session, c, check_exist=True)
            lb.rank_member(p.user_id, p.score, str(p.id))
        except Exception as e:
            logger.exception(msg="error updating the leaderboard")
            raise

    def get_leaderboard_by_category(self, session, c, check_exist=True):
        '''
        this routine will return a leaderboard if it exists. Note, by
        instantiating the leaderboard object we will create a leaderboard
        entry in the Redis cache. Since leaderboard entries are created by
        a separate service, we need to check if the leaderboard exists 
        via Redis directly.
        :param session: 
        :param c: category we are checking for 
        :return: leaderboard object, empty if leaderboard hasn't been created
        '''
        try:
            if check_exist and not self.leaderboard_exists(session, c):
                None

            lb = Leaderboard(self.leaderboard_name(c), host=self._redis_host, port=self._redis_port, page_size=10)
            return lb
        except Exception as e:
            logger.exception(msg="error getting leader board by category")
            return None

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
        try:
            p = session.query(photo.Photo).get(pid)
            if p.active == 0: # this photo has been de-activated, it might be offensive
                return None
            bimg = p.read_thumbnail_image()
            b64 = base64.standard_b64encode(bimg)
            b64_utf8 = b64.decode('utf-8')
            self._orientation = p.get_orientation()
            return b64_utf8
        except Exception as e:
            logger.exception(msg='error reading thumbnail!')
            return None

    def fetch_leaderboard(self, session, uid, c):
        '''
        read the leaderboard object and construct a list of 
        leaderboard dictionary elements for later jsonification
        :param session: database
        :param uid: user requesting leaderboard
        :param c: category for which leaderboard is request
        :return: list of of leaderboard dictionary elements or None if leaderboard doesn't exist
        '''

        try:
            lb = self.get_leaderboard_by_category(session, c, check_exist=True)
            if c is not None:
                logger.info(msg="retrieving leader board for category {}, \'{}\'".format(c.id, c.get_description()))
            else:
                logger.info(msg="retrieving leader board for category")

            dl = lb.leaders(1, page_size=10, with_member_data=True)   # 1st page is top 25
            lb_list = []
            for d in dl:
                lb_uid = int(str(d['member'], 'utf-8'))         # anonuser.id / userlogin.id
                try:
                    lb_pid = int(str(d['member_data'], 'utf-8'))    # photo.id
                except Exception as e:
                    continue

                lb_score = d['score']
                lb_rank = d['rank']
                if lb_uid == 0 or lb_pid == 0:  # we use a dummy value to persist leaderboard existance in daemon, filter it out
                    continue

                lb_name = self.create_displayname(session, lb_uid)
                b64_utf8 = self.read_thumbnail(session, lb_pid) # thumbnail image as utf-8 base64
                if b64_utf8 is not None: # problem with photo (such as it's offensive!)
                    if lb_uid == uid:
                        lb_list.append({'username': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'you':True, 'orientation': self._orientation, 'image' : b64_utf8})
                    else:
                        if usermgr.Friend.is_friend(session, uid, lb_uid):
                            lb_list.append({'username': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'isfriend':True, 'orientation': self._orientation, 'image' : b64_utf8})
                        else:
                            lb_list.append({'username': lb_name, 'score': lb_score, 'rank': lb_rank, 'pid': lb_pid, 'orientation': self._orientation, 'image' : b64_utf8})

            return lb_list
        except Exception as e:
            logger.exception(msg="error fetching leaderboard")
            if c is not None:
                logger.info(msg="leaderboard error for category id ={}".format(c.id))
            else:
                logger.info(msg="leaderboard error, no category specified")
            raise
