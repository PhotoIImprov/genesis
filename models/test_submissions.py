from unittest import TestCase
from models import userprofile
from models import category, photo, usermgr
from tests import DatabaseTest
import json

class TestSubmissions(DatabaseTest):

    def test_submissions_n_user(self):
        self.setup()
        prf = userprofile.Submissions(uid=None)
        try:
            d = prf.get_user_submissions(self.session, dir='next', cid=0)
            assert(False)
        except Exception as e:
            assert(True)
            pass

        self.teardown()

    def test_photos_for_categories_no_photos(self):
        self.setup()
        prf = userprofile.Submissions(uid=1)
        try:
            d = prf.photos_for_categories(self.session, 'next', 1)
            assert(not d)
        except Exception as e:
            assert(False)
            pass

        try:
            d = prf.photos_for_categories(self.session, 'prev', 1)
            assert(not d)
        except Exception as e:
            assert(False)
            pass

        self.teardown()

    def test_category_with_photos_none(self):
        self.setup()
        prf = userprofile.Submissions(uid=1)
        try:
            d = prf.categories_with_user_photos(self.session, 'next', 1)
            assert(not d)
        except Exception as e:
            assert(False)
            pass

        self.teardown()

    _photo_idx = None
    def photos_for_categories(self, session, dir: str, cid: int) -> list:
        pl = []
        for c in self._category_list:
            for i in range(1,c.id):
                p = photo.Photo()
                p.id = self._photo_idx
                self._photo_idx = self._photo_idx + 1
                p.category_id = c.id
                p.times_voted = i
                p.likes = i*2
                p.score = i*10
                pl.append(p)

        return pl

    _category_list = None
    def categories_with_user_photos(self, session, dir: str, cid: int) -> list:
        # let's create some categories
        cl = []
        for i in range(10,15):
            c = category.Category(category_id=i)
            c.state = category.CategoryState.UPLOAD
            c.start = '2017-08-{0}'.format(i)
            c.end = '2017-08-{0}'.format(i+4)
            c.description = 'category{0}'.format(c.id)
            cl.append(c)

        self._category_list = cl
        return cl

    def test_category_with_photos(self):
        self.setup()

        prf = userprofile.Submissions(uid=1, f_cat=self.categories_with_user_photos, p_cat=self.photos_for_categories)

        try:
            self._photo_idx = 1
            d = prf.get_user_submissions(self.session, 'next', 0)
            assert(bool(d))
            j_d = json.dumps(d)
        except Exception as e:
            assert(False)
            pass

        self.teardown()
