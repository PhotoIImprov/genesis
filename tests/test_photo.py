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
#        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        ft = open('../photos/Galaxy Edge 7 Office Desk (full res, hdr).jpg', 'rb')
        pi = photo.PhotoImage()
        pi._extension = 'JPEG'
        pi._binary_image = ft.read()

        for i in range(1, 50):
            email = 'bp100a_' + str(i) + '@gmail.com'
            auuid = str(uuid.uuid1()).replace('-','')
            au = usermgr.AnonUser.create_anon_user(self.session, auuid)
            if au is not None:
                u = usermgr.User.create_user(self.session, au.guid, email, 'pa55w0rd')
                fo = photo.Photo()
                fo.category_id = cid
                fo.save_user_image(self.session, pi, au.id, cid)
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
        pi = photo.PhotoImage()
        pi._binary_image = bytes("Now is the time for all good men", encoding='UTF-8')
        pi._extension = 'JPEG'
        photo.Photo.safe_write_file(guid, pi)

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

    def test_create_full_file_path(self):
        p = photo.Photo()
        p._sub_path = 'foo'
        p.create_full_path(None)
        assert(p.filepath == p._sub_path)

    def test_read_thumbnail_image_no_file(self):
        p = photo.Photo()
        p.filepath = "/mnt/image_files"
        p.filename = "foobar.gif"

        f = p.read_thumbnail_image()
        assert(f == None)

    def test_set_exif_data(self):
        pm = photo.PhotoMeta(640, 480)
        pm.set_exif_data(None)

    def test_make_dummy_exif(self):
        p = photo.Photo()
        d_exif = p.make_dummy_exif()
        gps_ifd = d_exif['GPS']
        assert(gps_ifd[29] == '1999:99:99 99:99:99')

    def test_save_user_image2(self):

        self.setup()

        fo = photo.Photo()
        pi = photo.PhotoImage()
        pi._extension = 'JPEG'

        # read our test file
        cwd = os.getcwd()
        if 'tests' in cwd:
            path = '../photos/Galaxy Edge 7 Office Desk (full res, hdr).jpg' #'../photos/Cute_Puppy.jpg'
        else:
            path = cwd + '/photos/Galaxy Edge 7 Office Desk (full res, hdr).jpg' #'/photos/Cute_Puppy.jpg'
        ft = open(path, 'rb')
        pi._binary_image = ft.read()

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
        fo.save_user_image(self.session, pi, u.id, c.id)
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

        pi = photo.PhotoImage()
        pi._binary_image = ft.read()
        pi._extension = 'JPEG'

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
            fo.save_user_image(self.session, pi, 0, c.id)
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)
            assert(e.args[1] == "invalid user")

        self.teardown()

    def test_save_fake_category_image(self):

        self.setup()

        fo = photo.Photo()
        assert (fo is not None)

        pi = photo.PhotoImage()

        # read our test file
        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        pi._binary_image = ft.read()
        pi._extension = 'JPEG'

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002673')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        try:
            fo.save_user_image(self.session, pi, u.id, 0)
        except BaseException as e:
            assert (e.args[0] == errno.EINVAL)
            assert (e.args[1] == "No Category found for cid=0")

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

    def test_generate_thumb_fail_no_image(self):
        fo = photo.Photo()
        assert (fo is not None)
        pi = photo.PhotoImage()
        fo._photoimage = pi
        try:
            fo.create_thumb()
        except BaseException as e:
            assert(e.args[0] == errno.EINVAL)

    def test_compute_scale_factor(self):
        p = photo.Photo()

        # 1280 x 360 -> 640 x 180
        height = 1280
        width = 720
        sf = p.compute_scalefactor(height*2, width*1)
        assert(sf == 0.5)

        # 360 x 1280 -> 180 x 640
        sf = p.compute_scalefactor(width*1, height*2)
        assert(sf == 0.5)

        # 1280 x 540 -> 640 x 270
        sf = p.compute_scalefactor(height*2, width*1.5)
        assert(sf == 0.5)

        # 1920 x 1440 -> 480 x 360
        sf = p.compute_scalefactor(height*3, width*4)
        assert(sf == 0.25)