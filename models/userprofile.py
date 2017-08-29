from dbsetup           import Base
import os, os.path, errno
import dbsetup
from models import category, usermgr, photo

'''
User Profile 
------------
All the user profile models are here
'''

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

        if num_categories is None:
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
                        p_element = {'pid': p.id, 'votes': p.times_voted, 'likes': p.likes, 'score': p.score,
                                     'url': 'preview/{0}'.format(p.id)}
                        cpl.append(p_element)

                if cpl:
                    category_dict = {'id':c.id, 'description':c.get_description(), 'end': str(c.end_date), 'start': str(c.start_date), 'state': category.CategoryState.to_str(c.state)}
                    category_submission = {'category': category_dict, 'photos': cpl}
                    return_dict.setdefault('submissions',[]).append(category_submission)

        return return_dict

