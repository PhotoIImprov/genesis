from unittest import TestCase

import initschema
import datetime
import os
import uuid

from models import resources

from models import category, photo, usermgr
from . import DatabaseTest
from random import randint

class TestPhoto(DatabaseTest):

    def create_test_photos(self, cid):
        # create a bunch of test photos for the specified category

        # read our test file
        ft = open('photos/Cute_Puppy.jpg', 'rb')
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
                fo.save_user_image(self.session, ph, "JPEG", au.id)
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

        self.setup()

        fo = photo.Photo()
        assert (fo is not None)

        data = bytes("Now is the time for all good men", encoding='UTF-8')

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
        fo.save_user_image(self.session, data, "JPEG", u.id)

        # now clean up
        os.remove(fo.filepath + "/" + fo.filename + ".JPEG")
        os.removedirs(fo.filepath)
        self.teardown()

    def test_save_user_image2(self):

        self.setup()

        fo = photo.Photo()
        assert (fo is not None)

        # read our test file
        ft = open('photos/Cute_Puppy.jpg', 'rb')
        assert (ft is not None)

        ph = ft.read()
        assert (ph is not None)

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category
        s_date = datetime.datetime.now()
        e_date = s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date)
        category.Category.write_category(self.session, c)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002673')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        fo.category_id = c.id
        fo.save_user_image(self.session, ph, "JPEG", u.id)
        fn = fo.filename

        fo.create_thumb()

        flist = photo.Photo.read_photo(self.session, u.id, c.id)

        assert (flist is not None)
        assert (len(flist) == 1)
        assert (flist[0].category_idx == 1)

        # now clean up
        os.remove(fo.filepath + "/" + fn + ".JPEG")  # our main image
        os.remove(fo.create_thumb_filename())  # our thumbnail
        os.removedirs(fo.filepath)

        self.teardown()


    def test_read_photos_by_index(self):

        self.setup()

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category
        s_date = datetime.datetime.now()
        e_date = s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date)
        category.Category.write_category(self.session, c)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002673')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        self.create_test_photos(c.id)

        indices = []
        pi = category.PhotoIndex.read_index(self.session, c.id)
        for i in range (0,9):
            rn = randint(0, pi.idx)
            if rn not in indices:
                indices.append(rn)

        p = photo.Photo.read_photos_by_index(self.session, u.id, c.id, indices)
        assert(p is not None)

        # now we need to clean up the files
        for i in range (0, pi.idx):
            indices = []
            indices.append(i)
            p = photo.Photo.read_photos_by_index(self.session, u.id, c.id, indices)
            if p is not None:
                try:
                    os.remove(p[0].filepath + '/' + p[0].filename + '.JPEG')
                    os.remove(p[0].create_thumb_filename())
                    os.removedirs(p[0].filepath)
                except:
                    pass

        self.teardown()

