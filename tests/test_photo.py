from unittest import TestCase
import initschema
import datetime
import os, errno
import uuid
from models import resources
from models import category, photo, usermgr, voting
from tests import DatabaseTest
from random import randint
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS, GPSTAGS
from io import BytesIO
import piexif
from sqlalchemy import func
import base64
import dbsetup
import iiServer
from flask import Flask

class TestPhoto(DatabaseTest):

    def create_test_photos(self, cid):
        # create a bunch of test photos for the specified category

        # read our test file
#        ft = open('../photos/Cute_Puppy.jpg', 'rb')
        ft = open('../photos/Galaxy Edge 7 Office Desk (full res, hdr).jpg', 'rb')
        pi = photo.PhotoImage()
        pi._extension = 'JPEG'
        pi._binary_image = ft.read()
        ft.close()

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
        pm = photo.PhotoMeta(640, 480, 'hashstring substitute')
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
        ft.close()

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
        ft.close()
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
        ft.close()
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

        # 1280 x 720 -> 720 x 720
        height = 1280
        width = 720
        sf = p.compute_scalefactor(height*1, width*1)
        assert(sf == 0.5625)

        # 720 x 1280 -> 720 x 1280
        sf = p.compute_scalefactor(width*1, height*1)
        assert(sf == 0.5625)

        # 1440 x 1280 -> 720 x 640
        sf = p.compute_scalefactor(1440, 1280)
        assert(sf == 0.5)

        # 1280 x 1440 -> 640 x 720
        sf = p.compute_scalefactor(1280, 1440)
        assert(sf == 0.5)

        # 640 x 720 -> 640 x 720
        sf = p.compute_scalefactor(640, 720)
        assert(sf == 1.0)

        # 720 x 640 -> 720 x 640
        sf = p.compute_scalefactor(720, 640)
        assert(sf == 1.0)

        # 640 x 480 -> 720 x 540
        sf = p.compute_scalefactor(640, 480)
        assert(sf == 1.125)

        # 480 x 640 -> 540 x 720
        sf = p.compute_scalefactor(480, 640)
        assert(sf == 1.125)

        # 480 x 480 -> 720 x 720
        sf = p.compute_scalefactor(480, 480)
        assert(sf == 1.5)

    def test_bad_exif_orientation(self):
        ft = open('../photos/Galaxy Edge 7 Office Desk (full res, hdr).jpg', 'rb')
        pi = photo.PhotoImage()
        pi._extension = 'JPEG'
        pi._binary_image = ft.read()
        ft.close()

        p = photo.Photo()
        p._photoimage = pi
        file_jpegdata = BytesIO(p._photoimage._binary_image)
        pil_img = Image.open(file_jpegdata)
        exif_dict = p.get_exif_dict(pil_img) # raw data from image
        exif_data = p.get_exif_data(pil_img) # key/value pairs reconstituted

        p.samsung_fix(exif_dict, exif_data)

        assert(exif_dict is not None)
        assert(exif_data is not None)

        exif_data_orientation = exif_data['Orientation']
        exif_dict_orientation = exif_dict['1st'][0x112]
        assert(exif_data_orientation == exif_dict_orientation)

    def test_exif_no_orientation(self):
        ft = open('../photos/bad_exif.jpg', 'rb')
        pi = photo.PhotoImage()
        pi._extension = 'JPEG'
        pi._binary_image = ft.read()
        ft.close()

        p = photo.Photo()
        p._photoimage = pi
        file_jpegdata = BytesIO(p._photoimage._binary_image)
        pil_img = Image.open(file_jpegdata)
        exif_dict = p.get_exif_dict(pil_img) # raw data from image
        exif_data = p.get_exif_data(pil_img) # key/value pairs reconstituted

        p.samsung_fix(exif_dict, exif_data)

        assert(exif_dict is not None)
        assert(exif_data is not None)
        assert(not 'Orientation' in exif_data)

    def test_watermark_application(self):
        # Open the original image
        # read our test file

        file_to_watermark = "no_watermark.jpeg"
        watermark_file = "ii_mainLogo_72.png"

        cwd = os.getcwd()
        if 'tests' in cwd:
            path = '../photos/'
        else:
            path = cwd + '/photos/'

        main = Image.open(path + file_to_watermark)
        info = main._getexif()
        exif_dict = piexif.load(main.info["exif"])
        exif_bytes = piexif.dump(exif_dict)
        orientation = exif_dict['0th'][0x112]

        rotate = 0
        if orientation in (5,6,7,8):
            rotate = 90

        # Create a new image for the watermark with an alpha layer (RGBA)
        #  the same size as the original image
        watermark = Image.new("RGBA", main.size)

        # Get an ImageDraw object so we can draw on the image
        waterdraw = ImageDraw.ImageDraw(watermark, "RGBA")

        # Place the text at (10, 10) in the upper left corner. Text will be white.
        font_path = "/usr/share/fonts/truetype/ubuntu-font-family/UbuntuMono-B.ttf"
        font = ImageFont.truetype(font=font_path, size=20)

        im = Image.open(path + watermark_file)
        im = im.convert("L")
        width, height = main.size
        im_width, im_height = im.size
        waterdraw.text((im_height + 10, height-20), "imageimprov", fill=(255,255,255, 128), font=font)
        if rotate == 90:
            watermark = watermark.rotate(90)
            im = im.rotate(90)

        # Get the watermark image as grayscale and fade the image
        # See <http://www.pythonware.com/library/pil/handbook/image.htm#Image.point>
        #  for information on the point() function
        # Note that the second parameter we give to the min function determines
        #  how faded the image will be. That number is in the range [0, 256],
        #  where 0 is black and 256 is white. A good value for fading our white
        #  text is in the range [100, 200].
        watermask = watermark.convert("L").point(lambda x: min(x, 100))
        im_mask = im.convert("L").point(lambda x: min(x, 100))

        # Apply this mask to the watermark image, using the alpha filter to
        #  make it transparent
        watermark.putalpha(watermask)
        im.putalpha(im_mask)
        im_x = width - im_width
        im_y = height - im_height

        # Paste the watermark (with alpha layer) onto the original image and save it
        main.paste(im=watermark, box=None, mask=watermark)
        main.paste(im=im, box=(im_x, im_y), mask=im_mask)
        main.save("/mnt/image_files/" + "with_watermark", format="JPEG", exif=exif_bytes)

    def test_read_thumbnail_by_id_with_watermark_invalid_pid(self):
        p = photo.Photo()
        self.setup()
        binary_img = p.read_thumbnail_by_id_with_watermark(self.session, 0)
        self.teardown()
        assert(binary_img is None)

    def test_read_thumbnail_by_id_with_watermark(self):
        self.setup()
        p = photo.Photo()
        pid = self.session.query(func.max(photo.Photo.id)).first()

        binary_img = p.read_thumbnail_by_id_with_watermark(self.session, pid[0])

        self.teardown()
        assert(binary_img is not None)

        path = dbsetup.image_store(dbsetup.determine_environment(None))
        fn = open(path + "/test_read_thumbnail.jpeg", "wb")
        fn.write(binary_img)
        fn.close()

    def test_iiServer_preview(self):
        self.setup()
        p = photo.Photo()
        pid = self.session.query(func.max(photo.Photo.id)).first()

        binary_image = p.read_thumbnail_by_id_with_watermark(self.session, pid[0])
        assert(binary_image is not None)

        self.teardown()