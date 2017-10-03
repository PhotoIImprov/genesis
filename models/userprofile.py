from dbsetup import Base
import os, os.path, errno
import dbsetup
from models import category, usermgr, photo
from models import engagement, voting

'''
User Profile 
------------
All the user profile models are here
'''
_MAX_PHOTOS_TO_RETURN = 50 # of photos that likes list will return


class Submissions():
    _uid = None

    _categories_with_user_photos = None
    _photos_for_categories = None

    def __init__(self, **kwargs):
        self._uid = kwargs.get('uid', None)
        # dependency injection...
        self._categories_with_user_photos = kwargs.get('f_cat', self.categories_with_user_photos)
        self._photos_for_categories = kwargs.get('p_cat', self.photos_for_categories)

    def categories_with_user_photos(self, session, dir: str, cid: int, num_categories: int) -> list:

        if dir == 'next':
            e = session.query(category.Category.id).filter(category.Category.id > cid). \
                join(photo.Photo, photo.Photo.category_id == category.Category.id). \
                filter(photo.Photo.user_id == self._uid). \
                order_by(category.Category.id.asc()). \
                distinct(category.Category.id)

            q = session.query(category.Category).filter(category.Category.id.in_(e)). \
                order_by(category.Category.id.asc())
        else:
            e = session.query(category.Category.id).filter(category.Category.id < cid). \
                join(photo.Photo, photo.Photo.category_id == category.Category.id). \
                filter(photo.Photo.user_id == self._uid). \
                order_by(category.Category.id.desc()) . \
                distinct(category.Category.id)

            q = session.query(category.Category).filter(category.Category.id.in_(e)). \
                order_by(category.Category.id.desc())

        cl = q.all()
        if cl is None or len(cl) == 0:
            return None

        if num_categories is None or num_categories >= len(cl):
            return cl

        return cl[:num_categories]

    def photos_for_categories(self, session, dir: str, cid: int) -> list:

        if dir == 'next':
            q = session.query(photo.Photo).filter(photo.Photo.user_id == self._uid) .\
                join(category.Category, category.Category.id == photo.Photo.category_id). \
                filter(category.Category.id > cid)
        else:
            q = session.query(photo.Photo).filter(photo.Photo.user_id == self._uid) .\
                join(category.Category, category.Category.id == photo.Photo.category_id). \
                filter(category.Category.id < cid)
        pl = q.all()
        return pl

    def get_user_submissions(self, session, dir: str, cid: int, num_categories: int) -> dict:
        if self._uid is None:
            raise

        # we need to construct a dictionary of the user's
        # submitted photos (just ids, not image data)

        au = usermgr.AnonUser.get_anon_user_by_id(session, self._uid)
        if au is None:
            raise

        user_info = {'id': self._uid, 'created_date': str(au.created_date)}
        return_dict = {'user': user_info}

        # get all the categories we care about
        cl = self._categories_with_user_photos(session, dir, cid, num_categories)
        if cl is not None:
            pl = self._photos_for_categories(session, dir, cid)
            for c in cl:
                # create category's photo list
                cpl = []
                for p in pl:
                    if p.category_id == c.id:
                        p_element = p.to_dict()
                        cpl.append(p_element)

                if cpl:
                    category_dict = {'id':c.id, 'description':c.get_description(), 'end': str(c.end_date), 'start': str(c.start_date), 'state': category.CategoryState.to_str(c.state)}
                    category_submission = {'category': category_dict, 'photos': cpl}
                    return_dict.setdefault('submissions',[]).append(category_submission)

        return return_dict

    @staticmethod
    def get_user_likes(session, au: usermgr.AnonUser, dir: str, cid: int) -> list:
        '''
        returns a list of the photos a user "likes" as list of
        jsonifyable dictionary elements

        dir - next/prev direction from specified photo_id (pid)
        cid - category to start next/prev search, non-inclusive
        :return:
        '''
        if dir == 'next':
            q = session.query(photo.Photo).filter(photo.Photo.category_id > cid). \
                join(engagement.Feedback, engagement.Feedback.photo_id == photo.Photo.id). \
                filter(engagement.Feedback.like > 0). \
                filter(engagement.Feedback.user_id == au.id)
            pl = q.all()

            # now get the categories...
            q = session.query(category.Category). \
                filter(category.Category.id > cid). \
                join(photo.Photo, photo.Photo.category_id == category.Category.id). \
                join(engagement.Feedback, engagement.Feedback.photo_id == photo.Photo.id). \
                filter(engagement.Feedback.like > 0). \
                filter(engagement.Feedback.user_id == au.id). \
                order_by(category.Category.id.asc())

        else:
            q = session.query(photo.Photo).filter(photo.Photo.category_id < cid). \
                join(engagement.Feedback, engagement.Feedback.photo_id == photo.Photo.id). \
                filter(engagement.Feedback.like > 0). \
                filter(engagement.Feedback.user_id == au.id)
            pl = q.all()

            # now get the categories...
            q = session.query(category.Category). \
                filter(category.Category.id < cid). \
                join(photo.Photo, photo.Photo.category_id == category.Category.id). \
                join(engagement.Feedback, engagement.Feedback.photo_id == photo.Photo.id). \
                filter(engagement.Feedback.like > 0). \
                filter(engagement.Feedback.user_id == au.id). \
                order_by(category.Category.id.desc())

        # okay we have a list of photos, now we need the categories for these photos...
        if pl is None:
            return None
        if len(pl) == 0:
            return None

        # okay we have some photos, which means we have some categories to fetch
        cl = q.all()
        if cl is None:
            return None
        if len(cl) == 0:
            return None

        # okay we have photos and categories, so we need to create our dictionary
        r = []
        num_photos = 0
        for c in cl:
            c_dict = c.to_json() # get jsonifyable dictionary
            p_dicts = []
            for p in pl:
                if c.id == p.category_id:
                    p_element = {'pid': p.id, 'votes': p.times_voted, 'likes': p.likes, 'score': p.score,
                                 'url': 'preview/{0}'.format(p.id), 'username':'tbd', 'isfriend': False}
                    p_dicts.append(p_element)

            # okay, if we have photos, create a dictionary element
            if len(p_dicts) > 0:
                element = {'category': c_dict, 'photos': p_dicts}
                r.append(element)
                num_photos = num_photos + len(p_dicts)
                if num_photos >= _MAX_PHOTOS_TO_RETURN:
                    return dict({'likes':r})

        return dict({'likes': r})

