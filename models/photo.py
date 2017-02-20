import sqlalchemy
from sqlalchemy.schema import DDL
from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey
import uuid
from dbsetup           import Base
import os, os.path, errno

import cv2
import numpy as np

class Photo(Base):

    __tablename__ = 'photo'

    id           = Column(Integer, primary_key = True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("userlogin.id"), nullable=False)
    category_id  = Column(Integer, ForeignKey("category.id"), nullable=False)
    category_idx = Column(Integer, nullable=True)
    filepath     = Column(String(500), nullable=False)                  # e.g. '/mnt/images/49269d/394f9/d431'
    filename     = Column(String(100), nullable=False, unique=True)     # e.g. '970797dfd9f149269d394f9d43179d64.jpeg'
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

# ======================================================================================================

    _uuid          = None
    _sub_path      = None
    _full_filename = None
    _mnt_point     = None   # "root path" to prefix, where folders are to be created
    _image_type    = None   # e.g. "JPEG", "PNG", "TIFF", etc.
    _raw_image     = None   # this is our unadulterated image file

# ======================================================================================================

    def set_image(self, image):
        if image is None:
            raise Exception(errno.EINVAL)

        self._raw_image = image
        return

    def get_image(self):
        return self._raw_image

    # okay, if the directory hasn't been created this will fail!
    @staticmethod
    def write_file(path_and_name, fdata):
        if fdata is None or path_and_name is None:
            raise Exception(errno.EINVAL)

        # okay we have a path and a filename, so let's try to create it
        fp = open(path_and_name, "wb")
        if fp is None:
            raise Exception(errno.EBADFD)

        fp.write(fdata)
        fp.close()
        return

    @staticmethod
    def mkdir_p(path):
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else: raise
        return

    @staticmethod
    def safe_write_file(path_and_name, fdata):
        # the path may not be created, so we try to write the file
        # catch the exception and try again

        write_status = False
        try:
            Photo.write_file(path_and_name, fdata)
        except OSError as err:
            # see if this is our "no such dir error
            if err.errno == errno.EEXIST:
                pass

            # we need to try and make this directory
            try:
                path_only = os.path.dirname(path_and_name)
                Photo.mkdir_p(path_only)
            except OSError as err:
                # this is a problem, not just someone beat us to creating the dir
                pass

            # try writing again
            Photo.write_file(path_and_name, fdata)

        return

    def create_name(self):
        self._uuid = uuid.uuid1()
        self.filename = str(self._uuid)
        return (self.filename)


    def create_sub_path(self):
        # paths are generated from filenames
        # paths are designed to hold no more 1000 entries,
        # so must be 10 bits in length. Three levels should give us 1 billion!

        # Note: The clock interval is 1E-7 (100ns). We are generating 2 million pictures
        #       per diem, which works out to 24 pictures/sec, or ~43 seconds to generate
        #       1000 pictures (filling up a directory). So we need to ignore the first
        #       29 bits of our timesequence. Hence the shifting and masking.
        #
        #       So ideally the lowest level directory will contain 1000 images,
        #       and each branch of directories will have 1000 sub-directories
        #       so three levels of this gives us a capacity for 1 billion images
        #       which is probably about 2 years of growth.

        # our filename is a uuid, we need to convert it back to one

        assert isinstance(self._uuid, object)
        dir1 = ( (self._uuid.time_low >> 29) & 0x7) + ((self._uuid.time_mid << 3) & 0x3F8)
        dir2 = ( (self._uuid.time_mid >> 3) & 0x3FF)
        dir3 = ( (self._uuid.time_mid >> 13) & 0x3FF)
        self._sub_path = '{:03}/{:03}/{:03}'.format( dir3, dir2, dir1)

        # The rest of the path needs to come from our configuration
        # The file name is the input UUID from which we generated the
        # path, so it's always unique. So it's:
        #
        # <configuration root path>/<generated path>/<uuid>.<filetype>
        #

    def create_full_path(self, rpath):
        # we should have our sub_path calculated. Now we need to
        # append the root to fully specify where the file shall go
        if rpath is None:
            self.filepath = self._sub_path
        else:
            self.filepath = rpath + "/" + self._sub_path

        return

    def create_full_filename(self):
        self._full_filename = self.filepath + "/" + self.filename + "." + self._image_type
        return self._full_filename

    def create_thumb_filename(self):
        thumb_filename = self.filepath + "/th_" + self.filename + ".png"
        return thumb_filename

    # SaveUserImage()
    # ===============
    # The user has uploaded an image, we need to save it to
    # the folder structure and save references in the
    # database
    def save_user_image(self, session, image_data, image_type, userlogin_id):
        if image_data is None or userlogin_id is None:
            raise errno.EINVAL

        self.set_image(image_data)
        self._image_type = image_type

        # okay we have aguments, lets create our file name
        self.create_name()
        self.create_sub_path()
        self.create_full_path(self._mnt_point)
        self.create_full_filename()

        # write to the folder
        Photo.safe_write_file(self._full_filename, image_data)

        # okay, now we need to save all this information to the
        self.user_id  = userlogin_id

        session.add(self)
        session.commit()


    def create_thumb(self):
        if self._raw_image is None:
            raise BaseException(errno.EINVAL)

        # from the supplied image, create a thumbnail
        # the original file has already been saved to the
        # filesystem, so we are just adding this file
        thumb_fn = self.create_thumb_filename()

        nparr = np.fromstring(self.get_image(), np.uint8)
        im = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        thumbnail = cv2.resize(im, (0,0), fx=0.5, fy=0.5)
        cv2.imwrite(thumb_fn, thumbnail)

    @staticmethod
    def read_photo(session, uid, cid):
        q = session.query(Photo).filter_by(user_id = uid, category_id = cid)
        p = q.all()

        return p

    # read_photos_by_index()
    # ======================
    # given a list of indices, will return a list of photos
    # that match for the sepcified category

    @staticmethod
    def read_photos_by_index(session, uid, cid, indices):
        if uid is None or cid is None or indices is None:
            raise BaseException(errno.EINVAL)

        q = session.query(Photo).filter(Photo.category_idx.in_(indices), Photo.category_id == cid )

        p = q.all()
        return p



# ====================================================================================================================

# register some DDL that we want attached to this model
sqlalchemy.event.listen(Photo.__table__, 'after_create',
             DDL('DROP FUNCTION IF EXISTS increment_photo_index;\n'
             'CREATE FUNCTION increment_photo_index(cid int) RETURNS int\n'
             'BEGIN\n'
             'DECLARE x int;\n'
             'update photoindex set idx = (@x:=idx)+1 where category_id = cid;\n'
             'return @x;\n'
             'END;\n'
             'DROP TRIGGER IF EXISTS pindexer;\n'
             'CREATE TRIGGER pindexer BEFORE INSERT ON photo FOR EACH ROW SET new.category_idx = increment_photo_index(NEW.category_id);'))




