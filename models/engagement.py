from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, Boolean, String
import dbsetup
from dbsetup import Base
from logsetup import logger
from models import resources
from models import usermgr, photo
from cache.ExpiryCache import _expiry_cache
import json
from enum import Enum

class RewardType(Enum):
    TEST = 0 # just for testing
    LIGHTBULB = 1 # lightbulb rewards
    DAYSPLAYED_30 = 2 # 30 days of consecutive playing
    DAYSPLAYED_100 = 3 # 100 days of consecutive playing
    DAYSPHOTO_7 = 4 # 7 days straight uploading photos
    DAYSPHOTO_30 = 5 # 30 days straight uploading photos
    DAYSPHOTO_100 = 6 # 100 days straight uploading photos

    @staticmethod
    def to_str(type: int) -> str:
        if type == RewardType.TEST.value:
            return "TEST"
        elif type == RewardType.LIGHTBULB.value:
            return "LIGHTBULB"

        return "UNKNOWN"

# some information on the various reward types
_REWARD_AMOUNTS = {RewardType.DAYSPLAYED_30.value: 5,
                   RewardType.DAYSPLAYED_100.value: 50,
                   RewardType.DAYSPHOTO_7.value: 5,
                   RewardType.DAYSPHOTO_30.value: 10,
                   RewardType.DAYSPHOTO_100: 50}

_REWARD_DAYSPAN = {RewardType.DAYSPLAYED_30.value: 30,
                   RewardType.DAYSPLAYED_100.value: 100,
                   RewardType.DAYSPHOTO_7.value: 7,
                   RewardType.DAYSPHOTO_30.value: 30,
                   RewardType.DAYSPHOTO_100.value: 100}

_REWARD_VALUES = {RewardType.LIGHTBULB.value: RewardType.LIGHTBULB.value,
                  RewardType.DAYSPLAYED_30.value: RewardType.LIGHTBULB.value,
                  RewardType.DAYSPLAYED_100.value: RewardType.LIGHTBULB.value,
                  RewardType.DAYSPHOTO_7.value: RewardType.LIGHTBULB.value,
                  RewardType.DAYSPHOTO_30.value: RewardType.LIGHTBULB.value,
                  RewardType.DAYSPHOTO_100.value: RewardType.LIGHTBULB.value}

class UserReward(Base):
    __tablename__ = 'userreward'

    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_userreward_userid"), primary_key=True, nullable=False)
    rewardtype = Column(String(32), nullable=False)
    current_balance = Column(Integer, default=0, nullable=True)
    total_balance = Column(Integer, default=0, nullable=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id', None)
        self.rewardtype = kwargs.get('rewardtype', None)
        self.current_balance = kwargs.get('quantity', 0)
        self.total_balance = self.current_balance

    def decrement_quantity(self, quantity: int) -> bool:
        if self.current_balance > quantity:
            self.current_balance -= quantity
            return True
        return False

    def update_quantity(self, quantity: int) -> int:
        self.current_balance += quantity
        self.total_balance += quantity
        return self.current_balance

class Reward(Base):
    __tablename__ = 'reward'

    id = Column(Integer, primary_key = True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_reward_userid"), primary_key=True, nullable=False)
    rewardtype = Column(String(32), nullable=False)
    quantity = Column(Integer, default=0, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)

    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id', None)
        self.rewardtype = kwargs.get('rewardtype', None)
        self.quantity = kwargs.get('quantity', None)


class Feedback(Base):
    __tablename__ = 'feedback'

    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_feedback_uid"), primary_key=True)
    photo_id = Column(Integer, ForeignKey("photo.id", name="fk_feedback_pid"), primary_key=True)
    like = Column(Boolean, nullable=False, default=False)
    offensive = Column(Boolean, nullable=False, default=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    _old_offensive = None
    _old_like = None
    def __init__(self, **kwargs):
        self.user_id = kwargs.get('uid', None)
        self.photo_id = kwargs.get('pid', None)
        self.like = kwargs.get('like', False)
        self.offensive = kwargs.get('offensive', False)

    def update_feedback(self, **kwargs) -> None:
        self._old_like = self.like
        self.like = kwargs.get('like', self._old_like)
        self._old_offensive = self.offensive
        self.offensive = kwargs.get('offensive', self._old_offensive)

    def update_photo(self, session, pid: int):
        '''
        update the # likes on the photo depending on how this user's
        like has changed things
        :param session:
        :param pid:
        :return:
        '''
        if self.like == self._old_like and self.offensive == self._old_offensive:
            return

        p = session.query(photo.Photo).get(pid)
        if self.like and not self._old_like:
            p.likes = p.likes + 1
        if not self.like and self._old_like:
            p.likes = p.likes - 1
        session.add(p)

class FeedbackTag(Base):
    __tablename__ = 'feedbacktag'

    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_feedbacktag_uid"), primary_key=True, nullable=False)
    photo_id = Column(Integer, ForeignKey("photo.id", name="fk_feedbacktag_pid"), primary_key=True, nullable=False)
    tags = Column(String(100), nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, **kwargs) -> None:
        self.user_id = kwargs.get('uid', None)
        self.photo_id = kwargs.get('pid', None)
        tags = kwargs.get('tags', None)
        if tags is not None:
            self.tags = json.dumps(tags)

    def update_feedbacktags(self, tags: list) -> None:
        self.tags = json.dumps(tags)

