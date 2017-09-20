from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, String, exc, func
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session
from sqlalchemy import exists, and_
import errno
from dbsetup import Base, Session, Configuration
from models import photo, category, usermgr, event
import sys
import json
import base64
from flask import jsonify
from leaderboard.leaderboard import Leaderboard
from models import error
from random import randint, shuffle
import redis
from cache.ExpiryCache import _expiry_cache
from logsetup import logger, timeit

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

    def __init__(self, cid: int, uid: int):
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

    def append_ballotentry(self, be) -> None:
        self._ballotentries.append(be)

    def read_photos_for_ballots(self, session) -> None:
        for be in self._ballotentries:
            be._photo = session.query(photo.Photo).get(be.photo_id)

    def append_tags_to_entries(self, c: category.Category) -> None:
        if len(c._categorytags) == 0:
            return

        # c_categorytags is a list of tags whereas be._tags is a JSON encoded array of tags
        for be in self._ballotentries:
            be._tags = c._categorytags

    def to_log(self) -> str:
        """
        Dump out the list of ballot entries as a string for the log
        :return: 
        """
        str_ballots = 'category_id={}\n '.format(self.category_id)
        for be in self._ballotentries:
            str_ballots += 'bid:{0}, photo:{1}\n'.format(be.id, be.photo_id)

        return str_ballots

    def to_json(self) -> list:

        ballots = []
        for be in self._ballotentries:
            ballots.append(be.to_json())
        return ballots

    @staticmethod
    def num_voters_by_category(session, cid: int) -> int:
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


    def to_json(self) -> dict:
        if self._photo is None:
            return None

        self._b64image = self._photo.read_thumbnail_b64_utf8()

        votes = self._photo.times_voted
        likes = self._photo.likes
        score = self._photo.score
        try:
            if self._tags is None:
                d = dict({'bid': self.id, 'orientation': 1, 'votes': votes, 'likes': likes, 'score': score,'image': self._b64image})
            else:
                d = dict({'bid':self.id, 'orientation': 1, 'votes': votes, 'likes': likes, 'score': score, 'tags': self._tags.to_str(), 'image':self._b64image})
        except Exception as e:
            raise

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

    def get_redis_server(self, session) -> dict:
        # read the database and find a redis server for us to use
        q = session.query(ServerList).filter_by(type = 'Redis').order_by(ServerList.created_date.desc())
        rs = q.first()
        ipaddress = '127.0.0.1'
        port = 6379
        if rs is not None:
            ipaddress = rs.ipaddress

        d = {'ip':ipaddress, 'port':port}
        return d
