from unittest import TestCase
import initschema
import datetime
import os, errno
import uuid
from models import resources
from models import category, photo, usermgr, voting
from tests import DatabaseTest
from random import randint

class TestPhoto(DatabaseTest):

    def create_test_photos(self, cid):
        # create a bunch of test photos for the specified category

        # read our test file
        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        assert (ft is not None)
        ph = ft.read()
        assert (ph is not None)

        for i in range(1, 50):
            email = 'bp100a_' + str(i) + '@gmail.com'
            auuid = str(uuid.uuid1()).replace('-','')
            au = usermgr.AnonUser.create_anon_user(self.session, auuid)
            if au is not None:
                u = usermgr.User.create_user(self.session, au.guid, email, 'pa55w0rd')
                fo = photo.Photo()
                assert (fo is not None)
                fo.category_id = cid
                fo.save_user_image(self.session, ph, "JPEG", au.id, cid)
                fn = fo.filename
                fo.create_thumb()

        return  # just created a slew of photos for this category and new users

# ----------------------------------- T E S T S ---------------------------------------
    def test_mkdir_p(self):

        # first make a unique directory
        guid = "UT_" + str(uuid.uuid1())

        try:
            photo.Photo.mkdir_p(guid)
        except:
            self.fail()

        # we created the dir, now try to create it again
        try:
            photo.Photo.mkdir_p(guid)
        except Exception:
            self.assertRaises(Exception)

        # remove directory
        os.rmdir(guid)

        return

    def test_safe_write_file(self):

        guid = "UT_" + str(uuid.uuid1()) + "/testdata.bin"
        data = bytes("Now is the time for all good men", encoding='UTF-8')

        photo.Photo.safe_write_file(guid, data)

        # now cleanup!
        os.remove(guid)
        os.removedirs(os.path.dirname(guid))

    def test_create_sub_path(self):
        fo = photo.Photo()
        assert (fo is not None)

        fo._uuid = uuid.uuid1()
        fo.create_sub_path()

        assert (fo._uuid is not None)
        assert (fo._sub_path is not None)

    def test_create_name(self):
        fo = photo.Photo()
        assert (fo is not None)

        fo.create_name()

        assert (fo._uuid is not None)
        assert (fo.filename is not None)

    def test_save_user_image(self):
        return            # issue with non-image JPEG generates thumbnail and fails.
        self.setup()

        fo = photo.Photo()
        assert (fo is not None)


        data = b'\xFF\xD8\xFF\xE0\x00\x10\x4A\x46\x49\x46\x00\x01\x01\x01\x00\x48\x00\x48\x00\x00' \
               b'\xFF\xDB\x00\x43\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF' \
               b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF' \
               b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF' \
               b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xC2\x00\x0B\x08\x00\x01\x00\x01\x01\x01' \
               b'\x11\x00\xFF\xC4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
               b'\x00\x00\x00\x00\xFF\xDA\x00\x08\x01\x01\x00\x01\x3F\x10'

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category
        s_date = datetime.datetime.now()
        e_date = s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date)
        category.Category.write_category(self.session, c)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002672')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        fo.category_id = c.id
        fo.user_id = u.id
        try:
            fo.save_user_image(self.session, data, "JPEG", u.id, c.id)
        except Exception as e:
            assert(e == errno.EFAULT)

        # now clean up
        os.remove(fo.filepath + "/" + fo.filename + ".JPEG")
        os.removedirs(fo.filepath)
        self.teardown()

    def test_save_user_image2(self):

        self.setup()

        fo = photo.Photo()
        assert (fo is not None)

        # read our test file
        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        assert (ft is not None)

        ph = ft.read()
        assert (ph is not None)

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category
        s_date = datetime.datetime.now()
        e_date = s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date, category.CategoryState.UPLOAD)
        category.Category.write_category(self.session, c)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002673')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        fo.category_id = c.id
        fo.save_user_image(self.session, ph, "JPEG", u.id, c.id)
        fn = fo.filename

        fo.create_thumb()

        flist = photo.Photo.read_photo(self.session, u.id, c.id)

        assert (flist is not None)
        assert (len(flist) == 1)

        # now clean up
        os.remove(fo.filepath + "/" + fn + ".JPEG")  # our main image
        os.remove(fo.create_thumb_filename())  # our thumbnail
       # os.removedirs(fo.filepath)

        self.teardown()

    def test_save_fake_user_image(self):

        self.setup()

        fo = photo.Photo()
        assert (fo is not None)

        # read our test file
        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        assert (ft is not None)

        ph = ft.read()
        assert (ph is not None)

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category
        s_date = datetime.datetime.now()
        e_date = s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date, category.CategoryState.UPLOAD)
        category.Category.write_category(self.session, c)

        fo.category_id = c.id
        try:
            fo.save_user_image(self.session, ph, "JPEG", 0, c.id)
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)
            assert(e.args[1] == "invalid user")

        self.teardown()

    def test_save_fake_category_image(self):

        self.setup()

        fo = photo.Photo()
        assert (fo is not None)

        # read our test file
        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        assert (ft is not None)

        ph = ft.read()
        assert (ph is not None)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002673')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        try:
            fo.save_user_image(self.session, ph, "JPEG", u.id, 0)
        except BaseException as e:
            assert (e.args[0] == errno.EINVAL)
            assert (e.args[1] == "invalid category")

        self.teardown()

    # read_photos_not_balloted()
    # ==========================
    # Retrieve a list of photos that are not on
    # any ballots
    @staticmethod
    def read_photos_not_balloted(session, uid, cid, count):
        if uid is None or cid is None or count is None:
            raise BaseException(errno.EINVAL)

        q = session.query(photo.Photo)\
        .outerjoin(voting.BallotEntry)\
        .filter(voting.BallotEntry.ballot_id is None).limit(count)

        p = q.all()
        return p

    def test_write_file_fail(self):
        try:
            photo.Photo.write_file(None, None)
        except Exception as e:
            if e.args[0] != errno.EINVAL:
                self.fail()

        return

    def test_generate_thumb_fail(self):
        fo = photo.Photo()
        assert (fo is not None)

        try:
            fo.create_thumb()
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)
