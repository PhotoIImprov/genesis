"""the controller for the category model. """
from datetime import datetime
from sqlalchemy import text
from sqlalchemy import func
from logsetup import logger
from models import resources
from models import usermgr, category, event, photo

# define some constants
_CATEGORYLIST_MAXSIZE = 100


class CategoryManager():
    _PHOTOLIST_MAXSIZE = 100
    _start_date = None
    _duration_upload = None
    _duration_vote = None
    _description = None

    def __init__(self, **kwargs):
        if len(kwargs) == 0:
            return
        try:
            str_start_date = kwargs.get('start_date', None)
            if str_start_date is not None:
                self._start_date = datetime.strptime(str_start_date, '%Y-%m-%d %H:%M')
        except ValueError as ve:
            msg = "error with date/time format {0}, format should be YYYY-MM-DD HH:MM, UTC time".\
                format(str_start_date)
            logger.exception(msg=msg)
            raise

        self._duration_upload = kwargs.get('upload_duration', 24)
        self._duration_vote = kwargs.get('vote_duration', 72)
        self._description = kwargs.get('description', None)

        # timedelta.seconds is a magnitude
        dtnow = datetime.now()
        time_difference = (dtnow - self._start_date).seconds
        if self._start_date > dtnow:
            time_difference = 0 - time_difference

        # validate arguments, start_date must be no more 5 minutes in the past
        if (type(self._duration_upload) is not int or self._duration_upload < 1 or self._duration_upload > 24*14) or \
           (type(self._duration_vote) is not int or self._duration_vote < 1 or self._duration_vote > 24 * 14) or \
           (time_difference > 300):
           raise Exception('CategoryManager', 'badargs')

    def create_resource(self, session, resource_string: str) -> resources.Resource:
        r = resources.Resource.find_resource_by_string(resource_string, 'EN', session)
        if r is not None:
            return r
        r = resources.Resource.create_new_resource(session, lang='EN', resource_str=resource_string)
        return r

    def create_category(self, session, type: int) -> category:
        """create a category in the db and return the object instance"""

        # look up resource, see if we already have it
        r = self.create_resource(session, self._description)

        # we have stashed (or found) our name, time to create the category
        c = category.Category(upload_duration=self._duration_upload, vote_duration=self._duration_vote, start_date=self._start_date, rid=r.resource_id, type=type)
        session.add(c)
        return c

    def active_categories_for_user(self, session, anonymous_user: usermgr.AnonUser) -> list:
        """
        ActiveCategoriesForUser()
        return a list of "active" categories for this user.

        "Active" means PENDING/VOTING/UPLOAD/COUNTING states
        "for User" means all open (public) categories and any categoties
        in events this user is participating in.
        :param session:
        :param u: an AnonUser object
        :return: <list> of categories
        """
        open_category_list = category.Category.all_categories(session, anonymous_user)
        try:
            query = session.query(category.Category). \
                join(event.EventCategory, event.EventCategory.category_id == category.Category.id). \
                join(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
                filter(category.Category.state != category.CategoryState.CLOSED.value) . \
                filter(event.EventUser.user_id == anonymous_user.id)

            event_category_list = query.all()
        except Exception as e:
            logger.exception(msg="error reading event category list for user:{}".format(anonymous_user.id))
            raise

        if event_category_list is None or len(event_category_list) == 0:
            return open_category_list

        # need to combine our lists
        combined_category_list = open_category_list + event_category_list

        return combined_category_list

    def category_photo_list(self, session, dir: str, pid: int, cid: int) -> list:
        """
        return a list of photos for the specified category
        :param session:
        :param pid: recent photo id to fetch from
        :param dir: "next" or "prev"
        :param cid: category identifier
        :return:
        """
        try:
            if (dir == 'next'):
                query = session.query(photo.Photo). \
                    filter(photo.Photo.category_id == cid). \
                    filter(photo.Photo.id > pid). \
                    order_by(photo.Photo.id.asc())
            else:
                query = session.query(photo.Photo). \
                    filter(photo.Photo.category_id == cid). \
                    filter(photo.Photo.id < pid). \
                    order_by(photo.Photo.id.desc())

            photo_list = query.all()
        except Exception as e:
            raise

        return photo_list[:self._PHOTOLIST_MAXSIZE]

    def photo_dict(self, photo_list: list) -> list:
        d_photos = []
        for photo in photo_list:
            d_photos.append(photo.to_dict())

        return d_photos

    @staticmethod
    def next_category_start(session) -> datetime:
        """"find the last category to finish with uploading, that's when we need to start this one"""
        query = session.query(func.max(func.date_add(category.Category.start_date, text("INTERVAL duration_upload HOUR")))).\
            filter(category.Category.state.in_([category.CategoryState.UPLOAD.value, category.CategoryState.UNKNOWN.value])).\
            filter(category.Category.type == category.CategoryType.OPEN.value)

        last_date = query.all()
        if last_date[0][0] is None:
            dt_last = datetime.now()
        else:
            dt_last = datetime.strptime(last_date[0][0], '%Y-%m-%d %H:%M:%S')
        return dt_last

    @staticmethod
    def copy_photos_from_previous_categories(session, cid: int) -> int:
        """
        Copy photo records from previous categories of the same name
        We'll call our stored procedure to do this work
        """
        stored_proc = 'CALL sp_CopyCategories(:cid)'
        results = session.execute(stored_proc, {'cid': cid})

        num_photos = photo.Photo.count_by_category(session, cid)
        return num_photos


