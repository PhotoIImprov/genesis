import sqlalchemy
from sqlalchemy.schema import DDL
from sqlalchemy        import Column, Integer, String, DateTime, text, ForeignKey, exc
import uuid
from dbsetup           import Base
import os, os.path, errno
import dbsetup
from models import category
import cv2
import numpy as np
import pymysql
import base64
import sys
from models import error

class Photo(Base):

    __tablename__ = 'photo'

    id           = Column(Integer, primary_key = True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("userlogin.id", name="fk_photo_user_id"), nullable=False, index=True)
    category_id  = Column(Integer, ForeignKey("category.id",  name="fk_photo_category_id"), nullable=False, index=True)
    filepath     = Column(String(500), nullable=False)                  # e.g. '/mnt/images/49269d/394f9/d431'
    filename     = Column(String(100), nullable=False, unique=True)     # e.g. '970797dfd9f149269d394f9d43179d64.jpeg'
    times_voted  = Column(Integer, nullable=False, default=0)           # number of votes on this photo
    score        = Column(Integer, nullable=False, default=0)           # calculated score based on ballot returns
    likes        = Column(Integer, nullable=False, default=0)           # number of "likes" given this photo
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

    @staticmethod
    def count_by_category(session, cid):
        # let's count how many photos are uploaded for this category
        c = session.query(Photo).filter_by(category_id = cid).count()
        return c

    def increment_vote_count(self):
        if self.times_voted is None:
            self.times_voted = 0

        self.times_voted += 1
        return

    def increment_likes(self):
        if self.likes is None:
            self.likes = 0

        self.likes += 1
        return

    def update_score(self, points):
        if self.score is None:
            self.score = 0

        self.score += points
        return self.score

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
                if err.errno == errno.EACCES:
                    # we don't have permissions to this folder! log it and fail
                    raise
                raise

            # try writing again
            Photo.write_file(path_and_name, fdata)

        return

    def create_name(self):
        self._uuid = uuid.uuid1()
        self.filename = str(self._uuid)
        return self.filename


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
        thumb_filename = self.filepath + "/th_" + self.filename + ".jpg"
        return thumb_filename

    # read_thumbnail_image()
    # ======================
    # returns the binary value of the thumbnail
    # associated with the photo record
    #
    def read_thumbnail_image(self):
        t_fn = self.create_thumb_filename()
        ft = open(t_fn, 'rb')
        if ft is None:
            return None
        thumb = ft.read()
        if thumb is None:
            return None

        return thumb

    # SaveUserImage()
    # ===============
    # The user has uploaded an image, we need to save it to
    # the folder structure and save references in the
    # database
    #
    # Note: We also create the thumbnail file as well
    def save_user_image(self, session, image_data, image_type, uid, cid):
        err = None
        if image_data is None or uid is None or cid is None:
            return {'error': error.iiServerErrors.INVALID_ARGS, 'arg': None}

        if not category.Category.is_upload_by_id(session, cid):
            return {'error': error.iiServerErrors.INVALID_ARGS, 'arg': None}

        self.set_image(image_data)
        self._image_type = image_type

        # okay we have arguments, lets create our file name
        self.create_name()      # our globally unique filename
        self.create_sub_path()  # a path to distribute the load
        self._mnt_point = dbsetup.image_store(dbsetup.determine_environment(None)) # get the mount point
        self.create_full_path(self._mnt_point) # put it all together
        self.create_full_filename()

        # write to the folder
        Photo.safe_write_file(self._full_filename, image_data)
        self.create_thumb()

        # okay, now we need to save all this information to the
        self.user_id  = uid
        self.category_id = cid

        try:
            session.add(self)
            session.commit()
        except exc.IntegrityError as e:
            if "fk_photo_user_id" in e.args[0]:
                raise BaseException(errno.EINVAL, "invalid user")
            if "fk_photo_category_id" in e.args[0]:
                raise BaseException(errno.EINVAL, "invalid category")
            raise

        return {'error': None, 'arg': self.filename}

    def create_thumb(self):
        if self._raw_image is None:
            raise BaseException(errno.EINVAL, "no raw image")

        # from the supplied image, create a thumbnail
        # the original file has already been saved to the
        # filesystem, so we are just adding this file
        thumb_fn = self.create_thumb_filename()

        nparr = np.fromstring(self.get_image(), np.uint8)
        im = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if im is None:
            raise Exception(errno.EFAULT)

        # Our resizing factor is based on the following:
        # max screen geometry is Samsung 7 = 2560 x 1440
        # we want to deliver 2 x 2 thumbnails, so 1/4 of
        # 2560x1440 -> 640x360
        #
        # Our input images vary from iPhone (3264x2448) to
        # Samsung (4032x3024), so scaling is 640/4032 -> ~16%
        # But we have to make sure we don't scale the iPhone
        # images too much.
        #
        # iPhone 7: 1340x750 -> 335x187
        # So we need to scale from the smallest input (iPhone)
        # to the largest output (Samsung)
        # 3264x2448 -> 640x360, which is about 20%
        try:
            thumbnail = cv2.resize(im, (0,0), fx=0.2, fy=0.2)
            cv2.imwrite(thumb_fn, thumbnail)
        except:
            e = sys.exc_info()[0]
            raise

    def read_photo_to_b64(self):
        self._image_type = "JPEG"       # need a better way of doing this!
        self.create_full_filename()
        f = open(self._full_filename, 'rb')
        if f is None:
            return None
        img = f.read()
        if img is None:
            return None

        b64_img = base64.standard_b64encode(img)
        return b64_img

    @staticmethod
    def last_submitted_photo(session, uid):
        if session is None or uid is None:
            return None
        q = session.query(Photo).filter(Photo.user_id == uid).order_by(Photo.created_date.desc())
        p = q.first() # top entry
        if p is not None:
            c = category.Category.read_category_by_id(session, p.category_id)
            b64img = p.read_photo_to_b64()
            return {'error':None, 'arg':{'image':b64img, 'category':c['arg']}}

        return {'error':"Nothing found", 'arg':None}

    @staticmethod
    def read_photo_by_filename(session, uid, fn):
        # okay the "filename" is the field stashed in the database
        q = session.query(Photo).filter_by(filename = fn)
        p = q.one()
        if p is None:
            return None

        return p.read_photo_to_b64()

    @staticmethod
    def read_photo(session, uid, cid):
        q = session.query(Photo).filter_by(user_id = uid, category_id = cid)
        p = q.all()

        return p

#    @staticmethod
#    def read_ballot_photos(session, b):
#        if session is None or b is None:
#            raise BaseException(errno.EINVAL)
#
#        idx_list = []
#        for be in b.get_ballotentries():
#            idx_list.append(be.photo_id)
#
#        p_list = Photo.read_photos_by_index(session, b.user_id, b.category_id, idx_list)
#        # we have the list of photo records, now use this to fetch the
#        # thumbnail images
#
#        return


# ====================================================================================================================

# register some DDL that we want attached to this model
sqlalchemy.event.listen(Photo.__table__, 'after_create',
             DDL('DROP PROCEDURE IF EXISTS sp_updateleaderboard;\n'
            'CREATE PROCEDURE sp_updateleaderboard (IN in_uid int, IN in_cid int, IN in_likes int, IN in_vote int, IN in_score int)\n'
            'this_proc: BEGIN\n'
            '  declare leaderboard_size int;\n'
            '  declare num_leaders int;\n'
            '  declare uid int;\n'
            '  declare min_score int;\n'
            '\n'
            '  set leaderboard_size = 10; -- we should get this from somewhere global...\n'
            '\n'
            '  -- The userboard isnt full, add the user (need to ensure we dont add more than num_leaders due to race condition)\n'
            '  select count(*) into num_leaders from leaderboard where category_id = in_cid;\n'
            '\n'
            '  -- Case #1: User is already on the leaderboard, update their record!\n'
            '  -- User already on leaderboard, update and leave\n'
            '  IF EXISTS(select * from leaderboard where user_id = in_uid AND category_id = in_cid) THEN\n'
            '      UPDATE leaderboard set score = in_score, likes = in_likes, votes = in_vote\n'
            '      where user_id = in_uid AND category_id = in_cid;\n'
            '\n'
            '      IF (ROW_COUNT() = 1) THEN -- race condition test\n'
            '        LEAVE this_proc;\n'
            '      END IF;\n'
            '  END IF;\n'
            '\n'
            '\n'
            '  -- Case #2: The leaderboard is full and we have a score that belongs on it (user is NOT on leaderboard due to Case #1)\n'
            '  IF (num_leaders >= leaderboard_size) AND EXISTS(select * from leaderboard where score < in_score and category_id = in_cid) THEN\n'
            '    -- identify the row we''re going to swap with\n'
            '    SELECT MIN(score) into min_score FROM leaderboard where category_id = in_cid;\n'
            '    SELECT user_id into uid FROM leaderboard where category_id = in_cid AND score = min_score LIMIT 1;\n'
            '    IF (ROW_COUNT() = 0) THEN -- race condition, score changed before we could get user_id\n'
            '      LEAVE this_proc;\n'
            '    END IF;\n'
            '\n'
            '    -- uid/min_score is the current record with the lowest score, overwrite!\n'
            '    IF (in_score > min_score) THEN\n'
            '      UPDATE leaderboard set user_id = in_uid, score = in_score, votes = in_vote, likes = in_likes\n'
            '      WHERE category_id = in_cid AND user_id = uid AND min_score = score;\n'
            '\n'
            '      -- If no rows affected, then race condition, regardless we are done here\n'
            '      LEAVE this_proc;\n'
            '    END IF;\n'
            '  END IF;\n'
            '\n'
            '  -- Case #3: Leader board is not full (user is NOT on leaderboard due to Case #1)\n'
            '  IF (num_leaders < leaderboard_size) THEN\n'
            '    -- okay we don''t have a full leaderboard\n'
            '    INSERT INTO leaderboard (score, likes, votes, user_id, category_id) VALUES(in_score, in_likes, in_vote, in_uid, in_cid);\n'
            '    IF (ROW_COUNT() = 1) THEN -- race condition test\n'
            '    LEAVE this_proc;\n'
            '    END IF;\n'
            '  END IF;\n'
            '\n'
            'END;\n'

            'DROP TRIGGER IF EXISTS highscores;\n'
            'CREATE TRIGGER highscores\n'
            'AFTER UPDATE\n'
            '  ON photo FOR EACH ROW\n'
            'BEGIN\n'
            '  CALL sp_updateleaderboard(NEW.user_id, NEW.category_id, NEW.likes, NEW.times_voted, NEW.score);\n'
            'END;\n'))





