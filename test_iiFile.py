from unittest import TestCase
import uuid
import iiFile
import errno
import os
import initschema.py


class TestIiFile(TestCase):
    def test_mkdir_p(self):

        # first make a unique directory
        guid = "UT_" + str(uuid.uuid1())

        try:
            iiFile.iiFile.mkdir_p(guid)
        except:
            self.fail()

        # we created the dir, now try to create it again
        try:
            iiFile.iiFile.mkdir_p(guid)
        except Exception:
            self.assertRaises(Exception)

        # remove directory
        os.rmdir(guid)

        return

    def test_safe_write_file(self):

        guid = "UT_" + str(uuid.uuid1()) + "/testdata.bin"
        data = bytes("Now is the time for all good men", encoding='UTF-8')

        iiFile.iiFile.safe_write_file(guid, data)

        # now cleanup!
        os.remove(guid)
        os.removedirs(os.path.dirname(guid))

    def test_create_sub_path(self):
        fo = iiFile.iiFile()
        assert (fo is not None)

        fo._uuid = uuid.uuid1()
        fo.create_sub_path()

        assert (fo._uuid is not None)
        assert (fo._sub_path is not None)

    def test_create_name(self):
        fo = iiFile.iiFile()
        assert (fo is not None)

        fo.create_name()

        assert (fo._uuid is not None)
        assert (fo.filename is not None)


    def test_save_user_image(self):
        fo = iiFile.iiFile()
        assert (fo is not None)

        data = bytes("Now is the time for all good men", encoding='UTF-8')

        fo.save_user_image(data, "JPEG", 1)

        # now clean up
        os.remove(fo.filepath + "/" + fo.filename + ".JPEG")
        os.removedirs(fo.filepath)

    def test_save_user_image2(self):
        fo = iiFile.iiFile()
        assert (fo is not None)


        # read our test file
        ft = open('photos/Cute_Puppy.jpg', 'rb')
        assert (ft is not None)

        photo = ft.read()
        assert (photo is not None)

        fo.save_user_image(photo, "JPEG", 1)
        fn = fo.filename

        fo.create_thumb()

        # now clean up
        os.remove(fo.filepath + "/" + fn + ".JPEG")           # our main image
        os.remove(fo.create_thumb_filename())  # our thumbnail
        os.removedirs(fo.filepath)
