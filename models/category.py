from sqlalchemy        import Column, Integer, DateTime, text, ForeignKey
from dbsetup           import Base
import errno
from datetime import datetime, timedelta
import dbsetup
from models import resources
from models import usermgr
from enum import Enum
from models import error
from leaderboard.leaderboard import Leaderboard # how we track high scores
# from iiMemoize import memoize_with_expiry, _memoize_cache

class CategoryState(Enum):
    UNKNOWN  = 0        # initial state
    UPLOAD   = 1        # category available for uploading photos, active
    VOTING   = 2        # category no longer accepting uploads, now we're voting on it, active
    COUNTING = 3        # category is no longer accepting votes, time to tabulate the votes
    CLOSED   = 4        # category is complete, votes have been tabulated

    @staticmethod
    def to_str(state):
        if state == CategoryState.UNKNOWN.value:
            return "UNKNOWN"
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
    state           = Column(Integer, nullable=False, default=CategoryState.UNKNOWN)
    round           = Column(Integer, nullable=False, default=0)
    resource_id     = Column(Integer, ForeignKey("resource.resource_id", name="fk_category_resource_id"), nullable=False)
    start_date      = Column(DateTime, nullable=False)
    duration_upload = Column(Integer, nullable=False, default=24)
    duration_vote   = Column(Integer, nullable=False, default=24)
    end_date        = Column(DateTime, nullable=False)


    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    _category_description = None
    # ======================================================================================================

    def __init__(self, **kwargs):
        self.id = kwargs.get('category_id', None)

    @staticmethod
    def get_description_by_resource(rid):
        session = dbsetup.Session()
        r = resources.Resource.load_resource_by_id(session, rid, 'EN')
        session.close()
        return r.resource_string

    def get_description(self):
        if self._category_description is None:
            self._category_description = Category.get_description_by_resource(self.resource_id)

        return self._category_description

    def to_json(self):
        category_description = self.get_description()
        json_start_date = "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(self.start_date.year, self.start_date.month, self.start_date.day, self.start_date.hour, self.start_date.minute, self.start_date.second)
        json_end_date   = "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(self.end_date.year, self.end_date.month, self.end_date.day, self.end_date.hour, self.end_date.minute, self.end_date.second)
        json_state = CategoryState.to_str(self.state)
        d = dict({'id':self.id, 'description':category_description, 'start':json_start_date, 'end':json_end_date, 'state':json_state, 'round': str(self.round)})
        return d

    def get_id(self):
        return self.id

    @staticmethod
    def list_to_json(cl):
        if cl is None or len(cl) == 0:
            return None

        categories = []
        for c in cl:
            categories.append(c.to_json())

        return categories

    @staticmethod
#    @memoize_with_expiry(_memoize_cache, 300, 0)
    def active_categories(session, uid):
        if session is None or uid is None:
            return None

        # see if the user id exists
        au = usermgr.AnonUser.get_anon_user_by_id(session,uid)
        if au is None:
            return None

        # display all categories that are in any of the three "Category States"
        # - UPLOAD - category can accept photos to be uploaded
        # - VOTING - category photos are ready for voting
        # - COUNTING - past voting, available to see status of winners
        q = session.query(Category).filter(Category.state.in_([CategoryState.UPLOAD.value, CategoryState.VOTING.value, CategoryState.COUNTING.value]))
        cl = q.all()

        for c in cl:
            session.expunge(c) # so they aren't tied to the session
        return cl

    @staticmethod
    def write_category(session, c):
        session.add(c)
        return

    @staticmethod
    def create_category(rid, sd, ed, st):
        c = Category()
        c.resource_id = rid
        c.start_date = sd
        c.end_date = ed
        c.state = st.value

        return c

    @staticmethod
    def read_category_by_id(session, cid):
        if session is None or cid is None:
            raise BaseException(errno.EINVAL)

        q = session.query(Category).filter_by(id = cid)
        c = q.one_or_none()
        err = None
        if c is None:
            err = error.iiServerErrors.INVALID_CATEGORY

        d = {'error': err, 'arg':c}
        return d

    def is_upload(self):
        return self.state == CategoryState.UPLOAD.value
    def is_voting(self):
        return self.state == CategoryState.VOTING.value

    @staticmethod
    def is_upload_by_id(session, cid):
        d = Category.read_category_by_id(session, cid)
        c = d['arg']
        if c is None:
            return False
        return c.state == CategoryState.UPLOAD.value

    @staticmethod
    def is_voting_by_id(session, cid):
        d = Category.read_category_by_id(session, cid)
        c = d['arg']
        if c is None:
            return False
        return c.state == CategoryState.VOTING.value
