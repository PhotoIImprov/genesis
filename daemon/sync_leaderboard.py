import sys
import time
import os
import daemon
from models import category, usermgr, photo, voting
import dbsetup.py
from datetime import timedelta, datetime, voting

_SCHEDULED_TIME_SECONDS = 60 * 10 # 10 minutes
_PAGE_SIZE_PHOTOS = 1000
_THROTTLE_UPDATES_SECONDS = 0.010 # 10 milliseconds between '_PAGE_SIZE_PHOTOS' record updates


class sync_daemon(Daemon):

    def run(self):
        while True:
            sleep(_SCHEDULED_TIME_SECONDS)
            session = dbsetup.Session()
            try:
                perform_task(session)
                session.commit()
            except:
                session.rollback()
            finally:
                session.close()

    def perform_task(self, session):
        cl = self.read_all_categories(session)
        for c in cl:
            self.scored_photos_by_category(session, c)

    def read_all_categories(self, session):
        earliest_category = datetime.now() + timedelta(days=-7)
        q = session.query(category.Category).filter(category.Category.start_date > earliest_category).\
            filter(category.Category.state != category.CategoryState.UNKNOWN.value)
        return q.all()

    def scored_photos_by_category(self, session, c):
        # there could be millions of records, so we need to page
        more_photos = True
        tm = voting.TallyMan()

        # see how many members are in the leaderboard vs. how many have scores
        members_in = tm.total_members_in_leaderboard(session, c)
        q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
            filter(photo.Photo.score > 0). \
            filter(photo.Photo.id > max_pid).order_by(photo.Photo.id.asc()).limit(_PAGE_SIZE_PHOTOS)
        scored_members = q.count()
        if members_in == scored_members:
            return

        max_pid = 0
        while more_photos:
            q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id).\
                filter(photo.Photo.score > 0).\
                filter(photo.Photo.id > max_pid).order_by(photo.Photo.id.asc()).limit(_PAGE_SIZE_PHOTOS)
            pl = q.all()
            more_photos = pl is not None
            max_pid = pl[0].pid
            for p in pl:
                tm.update_leaderboard(session, p.user_id, c.id, p)
                max_pid = p.id
            sleep(_THROTTLE_UPDATES_SECONDS) # brief pause so machine can catch it's breath

if __name__ == "__main__":
    daemon = sync_daemon(pidf='/var/run/synchronize_iiDaemon.pid', logf='/var/log/synchronize_iiDaemon.log')
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
