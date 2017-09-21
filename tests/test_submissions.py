from unittest import TestCase
from models import userprofile
from models import category, photo, usermgr, resources
from tests import DatabaseTest
import json
import uuid
from sqlalchemy import func
import datetime
from controllers import categorymgr
from models import engagement

class TestSubmissions(DatabaseTest):
    _cl = []

    def test_submissions_n_user(self):
        self.setup()
        prf = userprofile.Submissions(uid=None)
        try:
            d = prf.get_user_submissions(self.session, dir='next', cid=0)
            assert (False)
        except Exception as e:
            assert (True)
            pass

        self.teardown()

    def test_photos_for_categories_no_photos(self):
        self.setup()
        prf = userprofile.Submissions(uid=1)
        try:
            d = prf.photos_for_categories(self.session, 'next', 1)
            assert (not d)
        except Exception as e:
            assert (False)
            pass

        try:
            d = prf.photos_for_categories(self.session, 'prev', 1)
            assert (not d)
        except Exception as e:
            assert (False)
            pass

        self.teardown()

    def test_category_with_photos_none(self):
        self.setup()
        prf = userprofile.Submissions(uid=1)
        try:
            d = prf.categories_with_user_photos(self.session, 'next', 1, None)
            assert (not d)
        except Exception as e:
            assert (False)
            pass

        self.teardown()

    _photo_idx = None

    def photos_for_categories(self, session, dir: str, cid: int) -> list:
        pl = []
        for c in self._category_list:
            for i in range(1, c.id):
                p = photo.Photo()
                p.id = self._photo_idx
                self._photo_idx = self._photo_idx + 1
                p.category_id = c.id
                p.times_voted = i
                p.likes = i * 2
                p.score = i * 10
                pl.append(p)

        return pl

    _category_list = None

    def categories_with_user_photos(self, session, dir: str, cid: int, num_categories: int) -> list:
        # let's create some categories
        cl = []
        for i in range(10, 15):
            c = category.Category(category_id=i)
            c.state = category.CategoryState.UPLOAD
            c.start = '2017-08-{0}'.format(i)
            c.end = '2017-08-{0}'.format(i + 4)
            c.description = 'category{0}'.format(c.id)
            cl.append(c)

        self._category_list = cl
        return cl

    def test_category_with_photos(self):
        self.setup()

        prf = userprofile.Submissions(uid=1, f_cat=self.categories_with_user_photos, p_cat=self.photos_for_categories)

        try:
            self._photo_idx = 1
            d = prf.get_user_submissions(self.session, 'next', 0, None)
            assert (bool(d))
            j_d = json.dumps(d)
        except Exception as e:
            assert (False)
            pass

        self.teardown()

    def create_photos_for_category(self, uid: int, c, num_photos: int) -> list:

        pl = []
        for i in range (0,num_photos):
            p = photo.Photo()
            p.category_id = c.id
            p.filepath = 'boguspath'
            p.filename = str(uuid.uuid1()).translate({ord(c): None for c in '-'})
            p.user_id = uid
            p.times_voted = 0
            p.score = i*4
            p.likes = 0
            p.active = 1
            self.session.add(p)
            pl.append(p)

        self.session.commit()
        return pl

    def create_category_list(self, num_categories: int) -> list:
        cl = []
        for i in range(0, num_categories):
            guid = str(uuid.uuid1())
            category_description = guid.upper().translate({ord(c): None for c in '-'})
            start_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

            cm = categorymgr.CategoryManager(start_date=start_date, upload_duration=24, vote_duration=72, description=category_description)
            c = cm.create_category(self.session, category.CategoryType.OPEN.value)
            cl.append(c)
        return cl

    def create_anon_user(self):
        guid = str(uuid.uuid1())
        guid = guid.translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(self.session, guid)
        self.session.add(au)
        self.session.commit()
        return au

    def create_submissions_test_data(self, num_categories: int, num_photos: int)-> int:
        au = self.create_anon_user()
        self._cl = self.create_category_list(num_categories)
        assert(self._cl is not None)
        assert(len(self._cl) == num_categories)

        for c in self._cl:
            self.create_photos_for_category(au.id, c, num_photos)

        self.session.commit()
        return au.id


    def test_submissions_with_data(self):
        self.setup()

        num_categories = 10
        num_photos = 5
        uid = self.create_submissions_test_data(num_categories=num_categories, num_photos=num_photos)
        profile = userprofile.Submissions(uid=uid)
        d = profile.get_user_submissions(self.session, 'next', 0, None)
        assert(d is not None)
        assert(len(d) == 2)
        submissions = d['submissions']
        assert(len(submissions) == num_categories)
        json_d = json.dumps(d)

        submission_length = num_categories
        for submission in submissions:
            c = submission['category']
            cid = c['id']
            submission_length = submission_length - 1
            d_next = profile.get_user_submissions(self.session, 'next', cid, None)
            assert(d_next is not None)
            if submission_length > 0:
                c_submissions = d_next['submissions']
                assert(c_submissions is not None)
                assert(len(c_submissions) == submission_length)
            else:
                assert(not 'submissions' in d_next)

        submission_length = 0
        for submission in submissions:
            c = submission['category']
            cid = c['id']
            d_next = profile.get_user_submissions(self.session, 'prev', cid, None)
            assert(d_next is not None)
            if submission_length > 0:
                c_submissions = d_next['submissions']
                assert(c_submissions is not None)
                assert(len(c_submissions) == submission_length)
            else:
                assert(not 'submissions' in d_next)

            submission_length = submission_length + 1

        # our final act is make these all inactive
        for c in self._cl:
            c.state = category.CategoryState.CLOSED.value;

        self.session.commit()

        self.teardown()


    def test_submissions_with_no_data(self):
        self.setup()

        num_categories = 10
        guid = str(uuid.uuid1())
        guid = guid.translate({ord(c): None for c in '-'})
        au = usermgr.AnonUser.create_anon_user(self.session, guid)
        self.session.add(au)
        self.session.commit()

        profile = userprofile.Submissions(uid=au.id)
        d = profile.get_user_submissions(self.session, 'next', 0, None)
        assert(d is not None)
        created_date = d['user']['created_date']
        user_id = d['user']['id']
        assert(created_date is not None and user_id is not None)
        assert(user_id == au.id)

        self.teardown()

    def test_submissions_with_num_categories_next(self):
        self.setup()

        num_categories = 10
        uid = self.create_submissions_test_data(num_categories=num_categories, num_photos=5)
        profile = userprofile.Submissions(uid=uid)
        d = profile.get_user_submissions(self.session, 'next', 0, num_categories//2)
        assert(d is not None)
        assert(len(d) == 2)
        submissions = d['submissions']
        assert(len(submissions) == num_categories//2)
        json_d = json.dumps(d)

        self.teardown()

    def test_submissions_with_num_categories_prev(self):
        self.setup()

        num_categories = 10
        uid = self.create_submissions_test_data(num_categories=num_categories, num_photos=5)
        c = self._cl[num_categories//2]
        cid = c.id
        profile = userprofile.Submissions(uid=uid)
        d = profile.get_user_submissions(self.session, 'prev', cid, num_categories//2)
        assert(d is not None)
        assert(len(d) == 2)
        submissions = d['submissions']
        assert(len(submissions) == num_categories//2)
        json_d = json.dumps(d)

        self.teardown()

    def test_user_likes(self):
        self.setup()

        # Get a list of photos that user "likes".
        # Step #1 - create categories
        # Step #2 - create test users
        # Step #3 - create photos for test users for categories
        # Step #4 - create feedback (likes) for photos
        # Step #5 - have user request list of likes
        # Step #6 - validate list


        # Step #1
        num_categories = 5
        self.create_submissions_test_data(num_categories=num_categories, num_photos=5)

        # Step #2 - create users
        num_users = 5
        aul = []
        for i in range(0,num_users):
            au = self.create_anon_user()
            aul.append(au)

        # Step #3 - create photos
        pl = []
        num_photos = 2
        for c in self._cl:
            for au in aul:
                u_pl = self.create_photos_for_category(au.id, c, num_photos)
                pl = pl + u_pl

        # now create our anon user that will be "liking" things
        au = self.create_anon_user()

        # now cycle through our photos and create feedback (likes) for them
        for p in pl:
            fm = categorymgr.FeedbackManager(uid=au.id, pid=p.id, like=( (p.id & 0x1) == 1))
            fm.create_feedback(self.session)
        self.session.commit()

        # okay we'v written out a bunch of feedback
        user_likes = userprofile.Submissions.get_user_likes(self.session, au=au, dir='next', cid=0)
        assert(user_likes is not None)
        assert(len(user_likes['likes']) == len(self._cl))

        for cphotos in user_likes['likes']:
            c = cphotos['category']
            photos = cphotos['photos']
            for photo in photos:
                assert( (photo['pid'] & 0x1) == 1)
                assert(photo['likes'] == 1)

        self.teardown()

    def count_liked_photos(self, user_likes: list) -> int:
        total_photos = 0
        for cphotos in user_likes:
            c = cphotos['category']
            photos = cphotos['photos']
            total_photos += len(photos)

            for photo in photos:
                assert(photo['likes'] == 1)

        return total_photos

    def test_user_likes_paging(self):
        self.setup()

        # Get a list of photos that user "likes".
        # Step #1 - create categories
        # Step #2 - create test users
        # Step #3 - create photos for test users for categories
        # Step #4 - create feedback (likes) for photos
        # Step #5 - have user request list of likes
        # Step #6 - validate list


        # Step #1
        num_categories = 5
        self.create_submissions_test_data(num_categories=num_categories, num_photos=0)

        # Step #2 - create users
        num_users = 5
        aul = []
        for i in range(0,num_users):
            au = self.create_anon_user()
            aul.append(au)

        # Step #3 - create photos
        pl = []
        num_photos_per_user = 5
        for c in self._cl:
            for au in aul:
                u_pl = self.create_photos_for_category(au.id, c, num_photos_per_user)
                pl = pl + u_pl

        # now create our anon user that will be "liking" things
        au = self.create_anon_user()

        # now cycle through our photos and create feedback (likes) for them
        for p in pl:
            fm = categorymgr.FeedbackManager(uid=au.id, pid=p.id, like=True)
            fm.create_feedback(self.session)
        self.session.commit()

        # okay we'v written out a bunch of feedback
        user_likes = userprofile.Submissions.get_user_likes(self.session, au=au, dir='next', cid=0)
        assert(user_likes is not None)

        assert(self.count_liked_photos(user_likes['likes']) == userprofile._MAX_PHOTOS_TO_RETURN) # NOTE: The # photos per category needs to be be a factor of this value for the test to work

        # let's get the next 2 categories
        c = user_likes['likes'][len(user_likes['likes'])-1]['category']
        cid = c['id']

        next_user_likes = userprofile.Submissions.get_user_likes(self.session, au=au, dir='next', cid = cid)
        assert(self.count_liked_photos(next_user_likes['likes']) == userprofile._MAX_PHOTOS_TO_RETURN) # NOTE: The # photos per category needs to be be a factor of this value for the test to work

        # now page back
        c = next_user_likes['likes'][len(user_likes['likes'])-1]['category']
        cid = c['id']

        prev_user_likes = userprofile.Submissions.get_user_likes(self.session, au=au, dir='prev', cid = cid)
        assert(self.count_liked_photos(prev_user_likes['likes']) == userprofile._MAX_PHOTOS_TO_RETURN) # NOTE: The # photos per category needs to be be a factor of this value for the test to work

        self.teardown()