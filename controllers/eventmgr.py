"""the controller for the event model. """
from logsetup import logger
from models import usermgr, category, event, photo
from controllers import categorymgr


class EventManager():
    """Manages the Events"""
    _nl = [] # list of resources (strings)
    _cm_list = [] # list of categories manager objects that will create our categories
    _cl = [] # list of categories we created
    _e = None # our event object
    _ec_list = []
    _eu = None

    def __init__(self, **kwargs):
        self._nl = kwargs.get('categories', None)
        if self._nl is None:
            raise Exception('CategoryManager', 'badargs')

        vote_duration = kwargs.get('vote_duration', None)
        upload_duration = kwargs.get('upload_duration', None)
        start_date = kwargs.get('start_date', None)
        self._e = event.Event(**kwargs)

        self._cm_list = []
        for n in self._nl:
            c = categorymgr.CategoryManager(description=n, start_date=start_date, upload_duration=upload_duration, vote_duration=vote_duration)
            self._cm_list.append(c)

    @staticmethod
    def event_list(session, anonymous_user: usermgr.AnonUser, dir: str, cid: int) -> dict:
        """get a list of events for this user, pageable"""
        try:
            if dir == 'next':
                query = session.query(event.Event). \
                    join(event.EventUser, event.EventUser.event_id == event.Event.id). \
                    join(event.EventCategory, event.EventCategory.event_id == event.Event.id). \
                    filter(event.EventUser.user_id == anonymous_user.id). \
                    filter(event.EventCategory.category_id > cid)
            else:
                query = session.query(event.Event). \
                    join(event.EventUser, event.EventUser.event_id == event.Event.id). \
                    join(event.EventCategory, event.EventCategory.event_id == event.Event.id). \
                    filter(event.EventUser.user_id == anonymous_user.id). \
                    filter(event.EventCategory.category_id < cid)
        except Exception as e:
            raise

        list_of_events = query.all()
        if list_of_events is None or len(list_of_events) == 0:
            return None

        # now get the categories for the event list
        d_events = []
        for event_obj in list_of_events:
            event_obj.read_categories(session)
            d = event_obj.to_dict(uid=anonymous_user.id)
            d_events.append(d)
            for c in d['categories']:
                cpl = categorymgr.CategoryManager().category_photo_list(session, dir='next', pid=0, cid=c['id'])
                pl = []
                for p in cpl:
                    pl.append(p.to_dict())
                c['photos'] = pl

        return {'events': d_events}

    @staticmethod
    def join_event(session, accesskey: str, anonymous_user: usermgr.AnonUser) -> event.Event:
        """join the specified user to the event if they have the proper access key"""
        try:
            query = session.query(event.Event).\
                filter(event.Event.accesskey == accesskey)
            event_instance = query.one_or_none()
            if event_instance is None:
                raise Exception('join_event', 'event not found') # no such event

            # we have an event the user can join, so we need to create an EventUser
            # see if it already exists...
            query = session.query(event.EventUser). \
                filter(event.EventUser.user_id == anonymous_user.id). \
                filter(event.EventUser.event_id == event_instance.id)
            event_user = query.one_or_none()
            if event_user is None:
                event_user = event.EventUser(user=anonymous_user, event=event_instance, active=True)
                session.add(event_user)

            # get the categories for this event
            query = session.query(category.Category). \
                join(event.EventCategory, event.EventCategory.category_id == category.Category.id).\
                filter(event.EventCategory.event_id == event_instance.id)
            event_instance._cl = query.all()

            return event_instance
        except Exception as event_instance:
            logger.exception(msg='error joining event')
            raise

    def create_event(self, session) -> event.Event:
        """create an event object"""
        passphrases = PassPhraseManager().select_passphrase(session)
        self._e.accesskey = passphrases
        session.add(self._e)

        try:
            self._cl = []
            for cm in self._cm_list:
                category_instance = cm.create_category(session, type=category.CategoryType.EVENT.value)
                self._cl.append(category_instance)

            session.commit() # we need Event.id and Category.id values, so commit these objects to the DB

            # the event and all it's categories are created, so we have PKs,
            # time to make the EventCategory entries
            for category_instance in self._cl:
                event_category = event.EventCategory(category=category_instance, event=self._e, active=True)
                session.add(event_category)
                self._ec_list.append(event_category)

            # Tie the "creator" to the Event/Categories. If the creator is a player, they are "active" and can play
            self._eu = event.EventUser(user=self._e._u, event=self._e, active=(self._e._u.usertype == usermgr.UserType.PLAYER.value))
            session.add(self._eu)

            session.commit()    # now Category/Event/EventCategory/EventUser records all created, save them to the DB

        except Exception as e:
            logger.exception(msg="error creating event categories")

        return self._e

    @staticmethod
    def event_details(session, anonymous_user: usermgr.AnonUser, event_id: int) -> list:
        """fetch the details of the specified event"""
        try:
            e = session.query(event.Event).get(event_id)
            cl = e.read_categories(session)
            cl_dict = []
            for c in cl:
                (num_photos, num_users) = EventManager.category_details(session, c)
                c_dict = c.to_json()
                c_dict['num_players'] = num_users
                c_dict['num_photos'] = num_photos
                cl_dict.append(c_dict)

            e_dict = e.to_dict(anonymous_user.id)
            e_dict['categories'] = cl_dict
            return e_dict
        except Exception as e:
            logger.exception(msg="error fetching event {0}".format(event_id))
            raise

    @staticmethod
    def category_details(session, c: category.Category):
        try:
            num_photos = photo.Photo.count_by_category(session, c.id)
            num_users = photo.Photo.count_by_users(session, c.id)
            return num_photos, num_users
        except Exception as e:
            raise

    @staticmethod
    def events_for_user(session, anonymous_user: usermgr.AnonUser) -> list:
        """return all available events for the user as a dictionary list"""
        try:
            query = session.query(event.Event). \
                join(event.EventUser, event.EventUser.event_id == event.Event.id). \
                join(event.EventCategory, event.EventCategory.event_id == event.Event.id). \
                join(category.Category, category.Category.id == event.EventCategory.category_id). \
                filter(event.EventUser.user_id == anonymous_user.id). \
                filter(category.Category.state.in_([category.CategoryState.UPLOAD.value, category.CategoryState.VOTING.value, category.CategoryState.COUNTING.value, category.CategoryState.UNKNOWN.value]))
            event_list = query.all()

            # for each event, read in the categories
            eventlist_dict = []
            for event_instance in event_list:
                event_instance.read_categories(session)
                event_instance.read_userinfo(session)
                eventlist_dict.append(event_instance.to_dict(anonymous_user.id))

            return eventlist_dict # a dictionary suitable for jsonification
        except Exception as e:
            logger.exception(msg="events_for_user() failed to get event user list")
            raise


class PassPhraseManager():
    """selects a passphrase from the data.
    passphrases are 2 four character words that are randomly generated
    from a 'low entropy' list"""
    def select_passphrase(self, session) -> str:
        try:
            q = session.query(event.AccessKey). \
                filter(event.AccessKey.used == False). \
                order_by(event.AccessKey.hash). \
                with_for_update()

            access_key = q.first()
            access_key.used = True
            session.commit()
            return access_key.passphrase
        except Exception as e:
            raise Exception('select_passphrase', 'no phrases!')



