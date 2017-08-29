from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, Boolean, String
import dbsetup
from dbsetup import Base
from logsetup import logger
from models import resources
from models import usermgr, photo
from cache.ExpiryCache import _expiry_cache
import json

class UserReward(Base):
    __tablename__ = 'userreward'

    user_id = Column(Integer, ForeignKey("anonuser.id", name="fk_userreward_userid"), primary_key=True, nullable=False)
    rewardtype = Column(String(32), nullable=False)
    quantity = Column(Integer, default=0, nullable=False)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id', None)
        self.rewardtype = kwargs.get('rewardtype', None)
        self.quantity = kwargs.get('quantity', 0)

    def update_quantity(self, quantity: int) -> None:
        self.quantity = self.quantity + quantity

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

class RewardManager():
    _user_id = None
    _rewardtype = None
    def __init__(self, **kwargs):
        self._user_id = kwargs.get('user_id', None)
        self._rewardtype = kwargs.get('rewardtype', None)

    def create_reward(self, session, quantity: int) -> None:
        try:
            r = Reward(user_id=self._user_id, rewardtype=self._rewardtype, quantity=quantity)
            session.add(r)

            ur_l = session.query(UserReward).filter(user_id = self._user_id).filter(rewardtype = self._rewardtype).all()
            if ur_l is not None:
                ur = ur_l[0]
            if ur is None:
                ur = UserReward(user_id=self.user_id, rewardtype=self._rewardtype, quantity=0)

            ur.update_quantity(quantity)
            session.add(ur)
        except Exception as e:
            logger.exception(msg="error updating reward quantity")
            raise

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

class FeedbackManager():

    _uid = None
    _pid = None
    _like = False
    _offensive = False
    _tags = None

    def __init__(self, **kwargs):
        self._uid = kwargs.get('uid', None)
        self._pid = kwargs.get('pid', None)
        self._like = kwargs.get('like', False)
        self._offensive = kwargs.get('offensive', False)
        self._tags = kwargs.get('tags', None)

    def create_feedback(self, session) -> None:
        try:
            fb = session.query(Feedback).filter(Feedback.user_id == self._uid).filter(Feedback.photo_id == self._pid).one_or_none()
            if fb is None:
                fb = Feedback(uid=self._uid, pid=self._pid, like=self._like, offensive=self._offensive)
            else:
                fb.update_feedback(like=self._like, offensive=self._offensive)
            session.add(fb)

            if self._tags is not None:
                ft = session.query(FeedbackTag).filter(FeedbackTag.user_id == self._uid).filter(FeedbackTag.photo_id == self._pid).one_or_none()
                if ft is None:
                    ft = FeedbackTag(uid=self._uid, pid=self._pid, tags=self._tags)
                else:
                    ft.update_feedbacktags(self._tags)

                session.add(ft)

            fb.update_photo(session, self._pid)
        except Exception as e:
            logger.exception(msg="error creating feedback entry")
            raise