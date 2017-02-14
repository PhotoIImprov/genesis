from unittest import TestCase
import uuid
import iiFile
import errno
import os


class TestIiFile(TestCase):
    def test_mkdir_p(self):

        # first make a unique directory
        guid = str(uuid.uuid1())

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
        fo = iiFile.iiFile()
        assert(fo is not None)

        guid = str(uuid.uuid1()) + "/testdata.bin"
        data = bytes("Now is the time for all good men", encoding = 'UTF-8')

        fo.safe_write_file(guid, data)

        # now cleanup!
        os.remove(guid)
        os.rmdir(os.path.dirname(guid))
