import errno
from datetime import timedelta, datetime
from enum import Enum

from sqlalchemy import Column, Integer, DateTime, text, ForeignKey

import dbsetup
from cache.iiMemoize import memoize_with_expiry, _memoize_cache
from dbsetup import Base
from logsetup import logger
from models import resources
from models import usermgr
from cache.ExpiryCache import ExpiryCache, _expiry_cache

_CATEGORYLIST_MAXSIZE = 100

class CategoryState(Enum):
    UNKNOWN  = 0        # initial state
    UPLOAD   = 1        # category available for uploading photos, active
    VOTING   = 2        # category no longer accepting uploads, now we're voting on it, active
    COUNTING = 3        # category is no longer accepting votes, time to tabulate the votes
    CLOSED   = 4        # category is complete, votes have been tabulated

    @staticmethod
    def to_str(state):
        if state == CategoryState.UNKNOWN.value:
            return "PENDING"
        if state == CategoryState.UPLOAD.value:
            return "UPLOAD"
        if state == CategoryState.VOTING.value:
            return "VOTING"
        if state == CategoryState.COUNTING.value:
            return "COUNTING"
        if state == CategoryState.CLOSED.value:
            return "CLOSED"
        return "INVALID"

class Category(Base):
    __tablename__ = 'category'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    state           = Column(Integer, nullable=False, default=CategoryState.UNKNOWN, index=True)
    round           = Column(Integer, nullable=False, default=0)
    resource_id     = Column(Integer, ForeignKey("resource.resource_id", name="fk_category_resource_id"), nullable=False)
    start_date      = Column(DateTime, nullable=False, index=True)
    duration_upload = Column(Integer, nullable=False, default=24)
    duration_vote   = Column(Integer, nullable=False, default=24)
    end_date        = Column(DateTime, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    _category_description = None
    _categorytags = []
    # ======================================================================================================

    def __init__(self, **kwargs):
        self.id = kwargs.get('category_id', None)

    @staticmethod
    def get_description_by_resource(rid):
        session = dbsetup.Session()
        resource_string = None
        try:
            r = resources.Resource.load_resource_by_id(session, rid, 'EN')
            resource_string = r.resource_string
        except Exception as e:
            logger.exception(msg="error reading resource string for category")
        finally:
            session.close()
            return resource_string

    def get_description(self):
        if self._category_description is None:
            self._category_description = Category.get_description_by_resource(self.resource_id)

        return self._category_description

    def to_json(self):
        try:
            category_description = self.get_description()
            json_start_date = "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(self.start_date.year, self.start_date.month, self.start_date.day, self.start_date.hour, self.start_date.minute, self.start_date.second)
            _end_date = self.start_date + timedelta(hours=(self.duration_upload + self.duration_vote))
            json_end_date   = "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(_end_date.year, _end_date.month, _end_date.day, _end_date.hour, _end_date.minute, _end_date.second)
            json_state = CategoryState.to_str(self.state)
            d = dict({'id':self.id, 'description':category_description, 'start':json_start_date, 'end':json_end_date, 'state':json_state, 'round': str(self.round)})
            return d
        except Exception as e:
            logger.exception(msg="error json category values")
            raise

    def get_id(self):
        return self.id

    @staticmethod
    def list_to_json(cl):
        categories = []
        for c in cl:
            categories.append(c.to_json())
        return categories

    @staticmethod
#    @memoize_with_expiry(_memoize_cache, 300, 0)
    def all_categories(session, uid):
        # display all categories that are in any of the three "Category States"
        # - UPLOAD - category can accept photos to be uploaded
        # - VOTING - category photos are ready for voting
        # - COUNTING - past voting, available to see status of winners
        try:
            au = usermgr.AnonUser.get_anon_user_by_id(session, uid) # ensure we have a valid user context
            if au is None:
                return None

            # first check the cache
            cl = _expiry_cache.get("ALL_CATEGORIES")
            if cl is not None:
                return cl

            q = session.query(Category).filter(Category.state.in_([CategoryState.UPLOAD.value, CategoryState.VOTING.value, CategoryState.COUNTING.value, CategoryState.UNKNOWN.value]))
            cl = q.all()
            if cl is not None:
                del cl[_CATEGORYLIST_MAXSIZE:]    # limit list to 100 elements

            # if we are here then we had a cache miss, so let's stuff this in the cache
            # but set it's expiry to the earliest state change of a category in the list
            earliest = cl[0].start_date
            for c in cl:
                change_date = c.start_date # CategoryState.UNKNOWN
                if c.state == CategoryState.VOTING.value:
                    change_date = c.start_date + timedelta(hours=c.duration_upload + c.duration_vote)
                if c.state == CategoryState.UPLOAD.value:
                    change_date = c.start_date + timedelta(hours=c.duration_upload)

                if earliest > change_date:
                    earliest = change_date
                session.expunge(c) # while here, make sure the object isn't tied to a Session after it's in the cache

            expire_ttl = (earliest - datetime.now()).seconds
            assert(expire_ttl >= 0)
            if expire_ttl > 10: # just a sanity check in case ttl is negative
                _expiry_cache.put("ALL_CATEGORIES", cl, ttl=expire_ttl)
            return cl
        except Exception as e:
            logger.exception(msg='error reading active categories')
            raise

    @staticmethod
    def active_categories(session, uid):
        # display all categories that are in any of the three "Category States"
        # - UPLOAD - category can accept photos to be uploaded
        # - VOTING - category photos are ready for voting
        # - COUNTING - past voting, available to see status of winners
        try:
            cl = Category.all_categories(session, uid) # cached, returns counting
            if cl is not None:
                for c in cl:
                    if c.state == CategoryState.UNKNOWN.value:
                        cl.remove(c) # remove counting
            return cl
        except Exception as e:
            logger.exception(msg='error reading active categories')
            raise

    @staticmethod
    def write_category(session, c):
        session.add(c)

    @staticmethod
    def create_category(rid, sd, ed, st):
        c = Category()
        c.resource_id = rid
        c.start_date = sd
        c.end_date = ed
        c.state = st.value

        return c

    @staticmethod
#    @memoize_with_expiry(_memoize_cache, 300, 1)
    def read_category_by_id(cid, session):
        c = None
        try:
            c = session.query(Category).get(cid)
            if c is not None:
                c._categorytags = CategoryTagList().read_category_tags(cid, session)
        except Exception as e:
            logger.exception(msg="error reading category")
            session.rollback()
        finally:
            return c

    def is_upload(self):
        return self.state == CategoryState.UPLOAD.value
    def is_voting(self):
        return self.state == CategoryState.VOTING.value

    @staticmethod
    def is_upload_by_id(session, cid):
        c = Category.read_category_by_id(cid, session)
        if c is None:
            raise Exception(errno.EINVAL, 'No Category found for cid={}'.format(cid))

        return c.state == CategoryState.UPLOAD.value

class CategoryTag(Base):
    __tablename__ = 'categorytag'

    cid             = Column(Integer, ForeignKey("category.id", name="fk_categorytag_category_id"), primary_key=True)
    resource_id     = Column(Integer, ForeignKey("resource.resource_id", name="fk_categorytag_resource_id"), primary_key=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
     # ======================================================================================================

    def __init__(self, **kwargs):
        self.cid = kwargs.get('category_id', None)
        self.resource_id = kwargs.get('resource_id', None)

class CategoryTagList():
    _tags = None

#    @memoize_with_expiry(_memoize_cache, 3600, 1)
    def read_category_tags(self, cid, session):
        '''
        read the tags from the resource table
        :param cid:
        :param session:
        :return:
        '''
        try:
            q = session.query(resources.Resource).\
                join(CategoryTag, CategoryTag.resource_id == resources.Resource.resource_id).\
                filter(CategoryTag.cid == cid).\
                filter(resources.Resource.iso639_1 == 'EN')
            res = q.all()
            self._tags = []
            for r in res:
                self._tags.append(r.resource_string)
            return self._tags

        except Exception as e:
            logger.exception(msg='error reading category tags!')
            return None

    def to_str(self):
        return self._tags
