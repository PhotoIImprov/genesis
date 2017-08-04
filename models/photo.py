import sqlalchemy
from sqlalchemy.schema import DDL
from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey, exc
from sqlalchemy.orm import relationship
import uuid
from dbsetup           import Base
import os, os.path, errno
import dbsetup
from models import category
import pymysql
import base64
import sys
from models import error
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS, GPSTAGS
from io import BytesIO
import piexif
from retrying import retry
import json
import hashlib
from logsetup import logger, timeit
from cache.ExpiryCache import _expiry_cache
#import cv2
import numpy

class PhotoImage():
    _binary_image = None
    _extension = None
    def __init__(self):
        pass

class Photo(Base):

    __tablename__ = 'photo'
    __table_args__ = {'extend_existing':True}

    id           = Column(Integer, primary_key = True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("anonuser.id", name="fk_photo_user_id"), nullable=False, index=True)
    category_id  = Column(Integer, ForeignKey("category.id",  name="fk_photo_category_id"), nullable=False, index=True)
    filepath     = Column(String(500), nullable=False)                  # e.g. '/mnt/images/49269d/394f9/d431'
    filename     = Column(String(100), nullable=False, unique=True)     # e.g. '970797dfd9f149269d394f9d43179d64.jpeg'
    times_voted  = Column(Integer, nullable=False, default=0)           # number of votes on this photo
    score        = Column(Integer, nullable=False, default=0)           # calculated score based on ballot returns
    likes        = Column(Integer, nullable=False, default=0)           # number of "likes" given this photo
    active       = Column(Integer, nullable=False, default=1)           # if =0, then ignore the photo as if it didn't exist

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    _photometa = relationship("PhotoMeta", uselist=False, backref="photo", cascade="all, delete-orphan")

# ======================================================================================================

    _uuid          = None
    _sub_path      = None
    _full_filename = None
    _mnt_point     = None   # "root path" to prefix, where folders are to be created
    _orientation   = None   # orientation of the photo/thumbnail image
    _photoimage    = None
# ======================================================================================================

    def __init__(self, *args, **kwargs):
        self.id = kwargs.get('pid')

    @staticmethod
    def count_by_category(session, cid: int) -> int:
        # let's count how many photos are uploaded for this category
        num_photos = session.query(Photo).filter_by(category_id = cid).count()
        return num_photos

    def get_orientation(self) -> int:
        if self._orientation is None and self._photometa is not None:
            self._orientation = self._photometa.orientation
        return self._orientation

    def set_orientation(self, orientation: int) -> None:
        self._orientation = orientation

    # okay, if the directory hasn't been created this will fail!
    @staticmethod
    @timeit()
    def write_file(path_and_name: str, fdata: bytes) -> None:
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
    def mkdir_p(path: str) -> None:
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise
        return

    @staticmethod
    @retry(wait_exponential_multiplier=100, wait_exponential_max=1000, stop_max_attempt_number=10)
    def safe_write_file(path_and_name: str, pi:PhotoImage) -> None:
        # the path may not be created, so we try to write the file
        # catch the exception and try again
        try:
            Photo.write_file(path_and_name, pi._binary_image)
        except OSError as err:
            # see if this is our "no such dir error", if so we can try again, otherwise leave
            if err.errno != errno.ENOENT:
                raise
            # okay, the directory doesn't exist, so make it
            try:
                path_only = os.path.dirname(path_and_name)
                Photo.mkdir_p(path_only)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise

            # try writing again
            Photo.write_file(path_and_name, pi._binary_image)

        return

    def create_name(self) -> str:
        self._uuid = uuid.uuid1()
        self.filename = str(self._uuid)
        return self.filename


    def create_sub_path(self) -> None:
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

    def create_full_path(self, rpath: str) -> None:
        # we should have our sub_path calculated. Now we need to
        # append the root to fully specify where the file shall go
        if rpath is None:
            self.filepath = self._sub_path
        else:
            self.filepath = rpath + "/" + self._sub_path

        return

    def create_full_filename(self, extension: str) -> str:
        self._full_filename = self.filepath + "/" + self.filename + "." + extension
        return self._full_filename

    def create_storage_name(self, extension: str) -> str:
        self.create_name()      # our globally unique filename
        self.create_sub_path()  # a path to distribute the load
        self._mnt_point = dbsetup.image_store(dbsetup.determine_environment(None)) # get the mount point
        self.create_full_path(self._mnt_point) # put it all together
        return self.create_full_filename(extension)


    def create_thumb_filename(self) -> str:
        thumb_filename = self.filepath + "/th_" + self.filename + ".jpg"
        return thumb_filename

    def samsung_fix(self, exif_dict: dict, exif_data: list) -> None:
        try:
            if exif_data['Make'].decode('utf-8') != 'samsung':
                return
            if not 'Orientation' in exif_data:  # if orientation tags missing, pretty useless
                return

            image_orientation = exif_dict['0th'][0x112]
            thumb_orientation = exif_dict['1st'][0x112]

            if image_orientation != thumb_orientation:
                logger.info(msg="swapping orientation {0}->{1} for file {2}/{3}".format(image_orientation, thumb_orientation, self.filepath, self.filename))
                exif_data['Orientation'] = thumb_orientation
                exif_dict['0th'][0x112] = thumb_orientation
        except Exception as e:
            logger.exception(msg="Error with EXIF data parsing for file {0}/{1}".format(self.filepath, self.filename))

    def read_thumbnail_b64_utf8(self) -> str:
        try:
            b64_utf8 = _expiry_cache.get(self.filename)
            if b64_utf8 is not None:
                logger.info(msg="cache hit for thumb:{0}".format(self.filename))
                return b64_utf8

            t_fn = self.create_thumb_filename()
            image = Image.open(t_fn)

            b = BytesIO()
            image.save(b, format='JPEG')  # , exif=exif_bytes)
            thumb = b.getvalue()
            self.set_orientation(1)  # should always be '1'
            b64_bytes = base64.standard_b64encode(thumb)
            b64_utf8 = b64_bytes.decode('utf-8')
            _expiry_cache.put(self.filename, b64_utf8, ttl=60*60*24*3) # keep for 3 days
            return b64_utf8

        except Exception as e:
            str_e = str(e)
            logger.exception(msg='error reading thumbnail image')
            return None

    # SaveUserImage()
    # ===============
    # The user has uploaded an image, we need to save it to
    # the folder structure and save references in the
    # database
    #
    # Note: We also create the thumbnail file as well
    @timeit()
    def save_user_image(self, session, pi: PhotoImage, uid: int, cid: int) -> dict:
        err = None
        if pi._binary_image is None or uid is None or cid is None:
            return {'error': error.iiServerErrors.INVALID_ARGS, 'arg': None}

        if not category.Category.is_upload_by_id(session, cid):
            return {'error': error.iiServerErrors.INVALID_ARGS, 'arg': None}

        self._photoimage = pi

        # okay we have arguments, lets create our file name
        fn = self.create_storage_name('JPEG')

        # write to the folder
        Photo.safe_write_file(fn, pi)
        self.create_thumb_PIL(fn=None)

        # okay, now we need to save all this information to the
        self.user_id  = uid
        self.category_id = cid
        session.add(self)
        return {'error': None, 'arg': self.filename}


    def compute_scalefactor(self, height: int, width: int) -> float:
        '''
        :param height:
        :param width: 
        :return: a scaling factor such that the result is no dimension larger than _MAX_HEIGHT and _MAX_WIDTH
         yet retain aspect ratio
        '''
        _MAX_HEIGHT = 720
        _MAX_WIDTH = 720
        if height > width:
            sfh = _MAX_HEIGHT / height
            sfw = _MAX_WIDTH / width
        else:
            sfh = _MAX_HEIGHT / width
            sfw = _MAX_WIDTH / height

        sf = 1.0
        if sfh < sfw:
            sf = sfh
        else:
            sf = sfw

        return sf

    # get the raw exif data, not decoding
    @timeit()
    def get_exif_dict(self, pil_img: Image) -> dict:
        info = pil_img._getexif()
        if info is None:
            logger.warning(msg='no EXIF data in file, making dummy data file for {0}/{1}'.format(self.filepath, self.filename))
            return self.make_dummy_exif()

        return piexif.load(pil_img.info["exif"])

    # get the decoded exif data so we can pull out values
    @timeit()
    def get_exif_data(self, info: dict) -> dict:
        exif_data = {}
        if info is None:        # if image has not Exif data, make a dummy and return
            return None

        gps_data = {}
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo" or decoded == 'GPS':
                for t in value:
                    sub_decoded = GPSTAGS.get(t,t)
                    gps_data[sub_decoded] = value[t]
                exif_data[decoded] = gps_data
            else:
                if value is not None:
                    for t in value:
                        sub_decoded = TAGS.get(t, t)
                        if sub_decoded == 'GPSInfo':
                            exif_data[sub_decoded] = gps_data
                        else:
                            if type(sub_decoded) is str:
                                exif_data[sub_decoded] = value[t]


        return exif_data

    @timeit()
    def create_thumb_PIL(self, fn: str) -> None:
        '''
        We will "normalize" the thumbnail to an orientation of '1' to
        simplify any downstream processing. The orientation & exif data in
        photometa are for the hi-res image, which we don't mess with.

        :return: nothing
        '''
        if self._photoimage is None or self._photoimage._binary_image is None:
            raise BaseException(errno.EINVAL, "no raw image")

        file_jpegdata = BytesIO(self._photoimage._binary_image)
        digest = 0
        '''
        # stop computing the hash since now we are live and shouldn't have duplicates
        # if hash is '0' then no comparison for duplicates performed
        m = hashlib.md5()
        m.update(file_jpegdata.getvalue())
        digest = m.hexdigest()
        digest = digest.upper()
        '''
        pil_img = Image.open(file_jpegdata)
        exif_dict = self.get_exif_dict(pil_img) # raw data from image
        exif_data = self.get_exif_data(exif_dict) # key/value pairs reconstituted
        self.samsung_fix(exif_dict, exif_data)
        self.set_metadata(exif_data, pil_img.height, pil_img.width, digest) # set metadata about the hi-res Photo

        # Our thumbnail will be scaled down and normalized to an orientation of '1'
        rotate, flip = self.get_rotation_and_flip_PIL(exif_dict) # make sure we use Samsung fixed data!
        scalefactor = self.compute_scalefactor(pil_img.height, pil_img.width)
        new_size = (int(pil_img.width * scalefactor), int(pil_img.height*scalefactor))
        exif_dict['0th'][0x112] = 1  # we are normalizing to '1' for all thumbnails
        exif_bytes = None
        try:
            exif_bytes = piexif.dump(exif_dict)
        except Exception as e:
            logger.exception(msg='Error dumping EXIF bytes for file {}'.format(self._full_filename))

        th_img = pil_img.resize(new_size, resample=Image.LANCZOS)
        if rotate is not None:
            th_img = th_img.transpose(rotate)
        if flip is not None:
            th_img = th_img.transpose(flip)

        # from the supplied image, create a thumbnail
        # the original file has already been saved to the
        # filesystem, so we are just adding this file
        if fn is None:
            fn = self.create_thumb_filename()

        self.gcs_save_image(th_img, fn, exif_bytes)
        return

    # @timeit()
    # def create_thumb_OpenCV(self, fn=None) -> None:
    #     '''
    #     We will "normalize" the thumbnail to an orientation of '1' to
    #     simplify any downstream processing. The orientation & exif data in
    #     photometa are for the hi-res image, which we don't mess with.
    #
    #     :return: nothing
    #     '''
    #     if self._photoimage is None or self._photoimage._binary_image is None:
    #         raise BaseException(errno.EINVAL, "no raw image")
    #
    #     numpy_array = numpy.fromstring(self._photoimage._binary_image, dtype='uint8')
    #     img = cv2.imdecode(numpy_array, flags=cv2.IMREAD_COLOR)
    #     digest = 0
    #     (height, width) = img.shape[:2]
    #
    #     exif_dict = piexif.load(self._photoimage._binary_image)
    #     exif_data = self.get_exif_data(exif_dict) # key/value pairs reconstituted
    #     self.samsung_fix(exif_dict, exif_data)
    #     self.set_metadata(exif_data, height, width, digest)  # set metadata about the hi-res Photo
    #
    #     # Our thumbnail will be scaled down and normalized to an orientation of '1'
    #     rotate, flip = self.get_rotation_and_flip_OpenCV(exif_dict) # make sure we use Samsung fixed data!
    #     scalefactor = self.compute_scalefactor(height, width)
    #
    #     th_img = self.rotate_flip_scale(img, rotate, flip, scalefactor)
    #
    #     # from the supplied image, create a thumbnail
    #     # the original file has already been saved to the
    #     # filesystem, so we are just adding this file
    #     if fn is None:
    #         fn = self.create_thumb_filename()
    #
    #     exif_bytes = None
    #     try:
    #         exif_dict['0th'][0x112] = 1
    #         exif_bytes = piexif.dump(exif_dict)
    #     except Exception as e:
    #         logger.exception(msg=str(e))
    #
    #     self.gcs_save_image_fast(th_img, fn, exif_bytes)
    #     return

    def rotate_flip_scale(self, img, rotate_cw: int, flip: bool, scale: int):
        '''
        :param img: hi-res image
        :param rotate_cw: 0 or 90 degrees CW
        :param flip: 0 = flip X-axis, 1 = flip Y-axis, -1 = flip both axis
        :param scale: scale factor to scale down by
        :return: scaled, rotated & flipped image
        '''
        ret_img = cv2.resize(img, None,fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


        if rotate_cw == 90:
            ret_img = cv2.transpose(ret_img)
            ret_img = cv2.flip(ret_img, 1)

        if flip is not None:
            ret_img = cv2.flip(ret_img, flip)

        return ret_img

    # since Google Cloud storage can be flakey, we need to retry a couple of times. Between each
    # retry we need a random backup, with a maxium wait and # of times we'll retry.
    # so we are waiting for an exception to be thrown, then we go into our retrying...
    @retry(wait_exponential_multiplier=100, wait_exponential_max=1000, stop_max_attempt_number=10)
    def gcs_save_image(self, pil_img: Image, fn: str, exif_bytes: bytes) -> None:
        if exif_bytes is None:
            pil_img.save(fn)
        else:
            pil_img.save(fn, exif=exif_bytes)

    @retry(wait_exponential_multiplier=100, wait_exponential_max=1000, stop_max_attempt_number=10)
    def gcs_save_image_fast(self, img, fn: str, exif_bytes: bytes) -> bool:
        status = cv2.imwrite(fn, img)
        return status

    def make_dummy_exif(self) -> dict:
        zeroth_ifd = {piexif.ImageIFD.Make: u"Unknown",
                      piexif.ImageIFD.Orientation: 1,
                      piexif.ImageIFD.XResolution: (96, 1),
                      piexif.ImageIFD.YResolution: (96, 1),
                      piexif.ImageIFD.Software: u"piexif"
                      }
        exif_ifd = {piexif.ExifIFD.DateTimeOriginal: u"2099:09:29 10:10:10",
                    piexif.ExifIFD.LensMake: u"LensMake",
                    piexif.ExifIFD.Sharpness: 65535,
                    piexif.ExifIFD.LensSpecification: ((1, 1), (1, 1), (1, 1), (1, 1)),
                    }
        gps_ifd = {piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
                   piexif.GPSIFD.GPSAltitudeRef: 1,
                   piexif.GPSIFD.GPSDateStamp: u"1999:99:99 99:99:99",
                   }
        first_ifd = {piexif.ImageIFD.Make: u"Unknown",
                     piexif.ImageIFD.XResolution: (40, 1),
                     piexif.ImageIFD.YResolution: (40, 1),
                     piexif.ImageIFD.Software: u"piexif"
                     }
        exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd, "GPS": gps_ifd, "1st": first_ifd}

        return exif_dict

    def read_photo_to_b64(self) -> bytes:
        '''
        read_photo_to_b64()
        called infrequently when we need to return the full, hi-res image
        :return:
         bytes
        '''
        b64_img = None
        f = None
        try:
            self.create_full_filename('JPEG')
            f = open(self._full_filename, 'rb')
            img = f.read()
            b64_img = base64.standard_b64encode(img)
        except Exception as e:
            logger.exception(msg="error reading thumbnail to b64")
        finally:
            f.close()
        return b64_img


    @staticmethod
    def last_submitted_photo(session, uid: int) -> dict:
        q = session.query(Photo).filter(Photo.user_id == uid).order_by(Photo.created_date.desc())
        p = q.first() # top entry
        if p is not None:
            c = category.Category.read_category_by_id(p.category_id, session)
            b64img = p.read_photo_to_b64()
            return {'error':None, 'arg':{'image':b64img, 'category':c}}

        return {'error':"Nothing found", 'arg':None}

    @staticmethod
    def read_photo_by_filename(session, uid: int, fn: str) -> bytes:
        # okay the "filename" is the field stashed in the database
        q = session.query(Photo).filter_by(filename = fn)
        p = q.one()
        return p.read_photo_to_b64()

    @staticmethod
    def read_photo(session, uid: int, cid: int):
        q = session.query(Photo).filter_by(user_id = uid, category_id = cid)
        p = q.all()

        return p

    def get_rotation_and_flip_OpenCV(self, exif_dict: dict) -> tuple:
        """
        :param exif_dict: extracted EXIF dict from image
        :return: tuple of rotation (degrees) and axis flip (=0: vertical, =1: horizontal, -1: both)

           1        2       3      4         5            6           7          8

        888888  888888      88  88      8888888888  88                  88  8888888888
        88          88      88  88      88  88      88  88          88  88      88  88
        8888      8888    8888  8888    88          8888888888  8888888888          88
        88          88      88  88
        88          88  888888  888888

        Value	0th Row	    0th Column
        1	    top	        left side
        2	    top	        right side
        3	    bottom	    right side
        4   	bottom	    left side
        5	    left side	top
        6   	right side	top
        7	    right side	bottom
        8	    left side	bottom
        """

        rotate = 0
        flip = None
        try:
            orientation = exif_dict['0th'][0x112]
            if orientation in (5,6,7,8):
                rotate = 90
            if orientation in (4, 7):
                flip = 0
            if orientation in (2, 5):
                flip = 1
            if orientation in (3, 8):
                flip = -1
        except Exception as e:
            logger.exception(msg="error with EXIF/Orientation data")

        return rotate, flip

    def get_rotation_and_flip_PIL(self, exif_dict: dict) -> tuple:
        """
        :param exif_dict: extracted EXIF dict from image
        :return: tuple of rotation (degrees) and axis flip (=0: vertical, =1: horizontal, -1: both)

           1        2       3      4         5            6           7          8

        888888  888888      88  88      8888888888  88                  88  8888888888
        88          88      88  88      88  88      88  88          88  88      88  88
        8888      8888    8888  8888    88          8888888888  8888888888          88
        88          88      88  88
        88          88  888888  888888

        Value	0th Row	    0th Column
        1	    top	        left side
        2	    top	        right side
        3	    bottom	    right side
        4   	bottom	    left side
        5	    left side	top
        6   	right side	top
        7	    right side	bottom
        8	    left side	bottom
        """

        rotate = None
        flip = None
        try:
            orientation = exif_dict['0th'][0x112]
            if orientation in (5,6):
                rotate = Image.ROTATE_270
            if orientation in (3, 4):
                rotate = Image.ROTATE_180
            if orientation in (7,8):
                rotate = Image.ROTATE_90

            if orientation in (2, 4, 5, 7):
                flip = Image.FLIP_LEFT_RIGHT

        except Exception as e:
            logger.exception(msg="error with EXIF/Orientation data")

        return rotate, flip

    def get_watermark_font(self) -> ImageFont:
        # Place the text at (10, 10) in the upper left corner. Text will be white.
        font_path = dbsetup.get_fontname(dbsetup.determine_environment(None))
        font = ImageFont.truetype(font=font_path, size=20)
        return font

    def get_watermark_file(self) -> Image:
        watermark_file = "ii_mainLogo_72.png"
        path = dbsetup.resource_files(dbsetup.determine_environment(None))
        path += '/'
        im = Image.open(path + watermark_file)
        im = im.convert("L")
        return im

    def apply_watermark(self, img: Image) -> Image:
        # Create a new image for the watermark with an alpha layer (RGBA)
        #  the same size as the original image
        watermark = Image.new("RGBA", img.size)

        # Get an ImageDraw object so we can draw on the image
        waterdraw = ImageDraw.ImageDraw(watermark, "RGBA")

        font = self.get_watermark_font()
        im = self.get_watermark_file()

        width, height = img.size
        im_width, im_height = im.size
        waterdraw.text((im_width + 5, height - 20), "imageimprov", fill=(255, 255, 255, 128), font=font)

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
        im_x = 0
        im_y = height - im_height

        # Paste the watermark (with alpha layer) onto the original image and save it
        img.paste(im=watermark, box=None, mask=watermark)
        img.paste(im=im, box=(im_x, im_y), mask=im_mask)
        return img

    def read_thumbnail_by_id_with_watermark(self, session, pid: int) -> bytes:
        # Open the original image
        # read our test file

        try:
            p = session.query(Photo).get(pid)
            t_fn = p.create_thumb_filename()
            main = Image.open(t_fn)
            main = self.apply_watermark(main)
            b = BytesIO()
            main.save(b, 'JPEG')
            thumb = b.getvalue()
            return thumb
        except Exception as e:
            logger.exception(msg='error generating watermarked thumbnail!')
            return None


    def set_metadata(self, d_exif: dict, height: int, width: int, th_hash) -> None:
        self._photometa = PhotoMeta(height, width, th_hash)
        self._photometa.set_exif_data(d_exif)
        return

class PhotoMeta(Base):
    __tablename__ = 'photometa'
    __table_args__ = {'extend_existing':True}

    id          = Column(Integer, ForeignKey("photo.id", name="fk_photo_id"), primary_key = True)  # ties us back to our parent Photo record
    height      = Column(Integer, nullable=True)
    width       = Column(Integer, nullable=True)
    orientation = Column(String(500), nullable=True, index=True)
    gps         = Column(String(200), nullable=True)
    j_exif      = Column(String(2000), nullable=True)
    thumb_hash  = Column(String(64), nullable=True)

    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    def __init__(self, height: int, width: int, th_hash: str):
        self.height = height
        self.width = width
        if self.height > self.width:
            self.orientation = 8    # portrait (taller than wide)
        else:
            self.orientation = 1    # landscape (wider than tall)
        self.thumb_hash = th_hash

    def set_exif_data(self, d_exif: dict) -> None:
        if d_exif is None:
            return

        # we can't jsonify the byte arrays, and they probably aren't that useful (and awfully big!)
        d = {}
        for k in d_exif:
            v = d_exif[k]
            if type(v) is dict:
                d2 = {}
                for k1 in v:
                    v1 = v[k1]
                    if type(v1) is not bytes:
                        d2[k1] = v1
                d[k] = d2
            else:
                if type(v) is not bytes:
                    d[k] = v
        # ['Orientation']
        # ['GPSInfo']
        #   GPSLatitude
        #   GPSLatitudeRef
        #   GPSLongitude
        #   GPSLongitudeRef
        #
        # ['ExifImageHeight']
        # ['ExifImageWidth']

        self.j_exif = json.dumps(d)
        self.set_metadata_from_exif(d)
        return

    def set_metadata_from_exif(self, d: dict) -> None:
        self.gps = self.get_exif_location(d)
        if 'ExifImageHeight' in d:
            self.height = d['ExifImageHeight']
        if 'ExifImageWidth' in d:
            self.width = d['ExifImageWidth']
        if 'Orientation' in d:
            self.orientation = d['Orientation']

    def _get_if_exist(self, data, key):
        if key in data:
            return data[key]

        return None

    def _convert_to_minutes(self, value, ref) -> float:
        """
        Helper function to convert the GPS coordinates stored in the EXIF to degrees in float format
        :param value:
        :type value: exifread.utils.Ratio
        :rtype: float
        """
        d = float(value[0][0]) / float(value[0][1])
        m = float(value[1][0]) / float(value[1][1])
        s = float(value[2][0]) / float(value[2][1])

        s = '{}\xb0{}\x27{}"{}'.format(d, m, s, ref)
        return s

    def get_exif_location(self, exif_data: dict):
        # Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)
        if 'GPSInfo' in exif_data:
            gps_latitude = self._get_if_exist(exif_data['GPSInfo'], 'GPSLatitude')
            gps_latitude_ref = self._get_if_exist(exif_data['GPSInfo'], 'GPSLatitudeRef')
            gps_longitude = self._get_if_exist(exif_data['GPSInfo'], 'GPSLongitude')
            gps_longitude_ref = self._get_if_exist(exif_data['GPSInfo'], 'GPSLongitudeRef')

            if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
                s_lat = self._convert_to_minutes(gps_latitude, gps_latitude_ref)
                s_lon = self._convert_to_minutes(gps_longitude, gps_longitude_ref)
                return s_lat + s_lon

        return None
