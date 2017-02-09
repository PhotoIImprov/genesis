from sqlalchemy        import Column, Integer, String, DateTime, text
import uuid
from dbsetup           import Session, Base, engine, metadata

class iiFile(Base):

    __tablename__ = 'iifile'

    id           = Column(Integer, primary_key = True, autoincrement=True)
    user_id      = Column(Integer, nullable=False)
    filepath     = Column(String(500), nullable=False)                  # e.g. '/mnt/images/49269d/394f9/d431'
    filename     = Column(String(100), nullable=False, unique=True)     # e.g. '970797dfd9f149269d394f9d43179d64.jpeg'
    created_date = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    last_updated = Column(DateTime, nullable=True, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP') )

    _uuid          = None
    _filename      = None
    _sub_path      = None
    _full_path     = None
    _full_filename = None

    def create_name(self):
        self._uuid = uuid.uuid1()
        self._filename = str(self._uuid)
        return (self._filename)


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
        self._sub_path = '{}/{}/{}'.format( dir3, dir2, dir1)

        # The rest of the path needs to come from our configuration
        # The file name is the input UUID from which we generated the
        # path, so it's always unique. So it's:
        #
        # <configuration root path>/<generated path>/<uuid>.<filetype>
        #
    def create_full_path(self, root_path):
        # we should have our sub_path calculated. Now we need to
        # append the root to fully specify where the file shall go
        self._full_path = root_path + '/' + self._sub_path
        return self._full_path

    def create_full_filename(self, full_path):
        self._full_filename = (full_path or self.full_path) + self.filename
        return self._full_filename