import sys
import time
import os

lib_path = os.path.abspath(os.path.join('..'))
sys.path.append(lib_path)

from python_daemon import Daemon
import redis
from models import category, usermgr, photo, voting
import dbsetup
from datetime import timedelta, datetime

_SCHEDULED_TIME_SECONDS_DEV = 1
_SCHEDULED_TIME_SECONDS_PROD = 60 * 10 # 10 minutes
_PAGE_SIZE_PHOTOS = 1000
_THROTTLE_UPDATES_SECONDS = 0.010 # 10 milliseconds between '_PAGE_SIZE_PHOTOS' record updates

class sync_daemon(Daemon):

    _pidf = None
    _logf = None
    _redis_host = None
    _redis_port = None
    _redis_conn = None
    _current_lbname = None

    def __init__(self,*args, **kwargs):
        self._pidf = kwargs.get('pidf')
        self._logf = kwargs.get('logf')

    def run(self):
        env = dbsetup.determine_environment(None)
        if env == dbsetup.EnvironmentType.DEV:
            schedule_time = _SCHEDULED_TIME_SECONDS_DEV
        else:
            schedule_time = _SCHEDULED_TIME_SECONDS_PROD

        print ("sleep time %d seconds" % (schedule_time))

        while True:
            time.sleep(schedule_time)
            session = dbsetup.Session()
            try:
                self.perform_task(session)
                session.commit()
            except:
                session.rollback()
            finally:
                session.close()

    def perform_task(self, session):
        cl = self.read_all_categories(session)
        tm = voting.TallyMan()
        for c in cl:
            self.scored_photos_by_category(session, tm, c)

    def read_all_categories(self, session):
        earliest_category = datetime.now() + timedelta(days=-7)
        q = session.query(category.Category).filter(category.Category.start_date > earliest_category).\
            filter(category.Category.state != category.CategoryState.UNKNOWN.value)
        return q.all()

    def leaderboard_exists(self,session, tm, c):
        if self._redis_conn is None:
            sl = voting.ServerList()
            d = sl.get_redis_server(session)
            self._redis_host = d['ip']
            self._redis_port = d['port']
            self._redis_conn = redis.Redis(host=self._redis_host, port=self._redis_port)

        self._current_lbname = tm.leaderboard_name(c)
        return self._redis_conn.exists(self._current_lbname)

    def scored_photos_by_category(self, session, tm, c):
        # there could be millions of records, so we need to page
        print ("category %d" % (c.id))
        if self.leaderboard_exists(session, tm, c):
            return
        print("leaderboard does not exist for category %d" % (c.id))
        tm.get_leaderboard_by_category(session, c)

        more_photos = True
        max_pid = 0
        while more_photos:
            print("...read 1000 records")
            q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id).\
                filter(photo.Photo.score > 0).\
                filter(photo.Photo.id > max_pid).order_by(photo.Photo.id.asc()).limit(_PAGE_SIZE_PHOTOS)
            pl = q.all()
            more_photos = len(pl) > 0
            if more_photos:
                max_pid = pl[0].id
                for p in pl:
                    tm.update_leaderboard(session, c, p, check_exist=False)
                    max_pid = p.id

            time.sleep(_THROTTLE_UPDATES_SECONDS) # brief pause so machine can catch it's breath

# ================================================================================================================

if __name__ == "__main__":
    daemon = sync_daemon(pidf='/var/run/synchronize_iiDaemon.pid', logf='/var/log/synchronize_iiDaemon.log')

    daemon.run()
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            deamon.start()
        elif 'stop' == sys.argv[1]:
            deamon.stop()
        elif 'restart' == sys.argv[1]:
            dameon.restart()
        else:
            print("unknown command")
            sys.exit(2)
        sys.exit(0)
    else:
        print("usage: %s start|stop|restart" & sys.argv[0])
        sys.exit(2)
