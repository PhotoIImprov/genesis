import datetime
import os
import uuid

from models import resources

from models import category, photo, usermgr
from . import DatabaseTest


class TestPhoto(DatabaseTest):


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
        fo.user_id     = u.id
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

        photo = ft.read()
        assert (photo is not None)

        # first we need a resource
        r = resources.Resource.create_resource(5555, 'EN', 'Kittens')
        resources.Resource.write_resource(self.session, r)

        # now create our category
        s_date = datetime.datetime.now()
        e_date =  s_date + datetime.timedelta(days=1)
        c = category.Category.create_category(r.resource_id, s_date, e_date)
        category.Category.write_category(self.session, c)

        # create a user
        au = usermgr.AnonUser.create_anon_user(self.session, '99275132efe811e6bc6492361f002673')
        if au is not None:
            u = usermgr.User.create_user(self.session, au.guid, 'harry.collins@gmail.com', 'pa55w0rd')

        fo.category_id = c.id
        fo.save_user_image(self.session, photo, "JPEG", u.id)
        fn = fo.filename

        fo.create_thumb()

        flist = photo.Photo.read_photo(self.session, u.id, c.id)

        assert(flist is not None)
        assert(len(flist) == 1)
        assert(flist[0].category_idx == 1)

        # now clean up
        os.remove(fo.filepath + "/" + fn + ".JPEG")           # our main image
        os.remove(fo.create_thumb_filename())  # our thumbnail
        os.removedirs(fo.filepath)

        self.teardown()
