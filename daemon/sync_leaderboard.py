#!/usr/bin/env python

import sys
import time
import os
from controllers import categorymgr

lib_path = os.path.abspath(os.path.join('..'))
sys.path.append(lib_path)

from python_daemon import myDaemon
import redis
from models import category, usermgr, photo, voting
import dbsetup
from datetime import timedelta, datetime

from logsetup import logger
from models import sql_logging

import daemon

_SCHEDULED_TIME_SECONDS_DEV = 5
_SCHEDULED_TIME_SECONDS_PROD = 60 * 5 # 5 minutes for testing
_PAGE_SIZE_PHOTOS = 1000
_THROTTLE_UPDATES_SECONDS = 0.010 # 10 milliseconds between '_PAGE_SIZE_PHOTOS' record updates

class sync_daemon(myDaemon):

    _pidf = None
    _logf = None
    _redis_host = None
    _redis_port = None
    _redis_conn = None
    _current_lbname = None

    def __init__(self,*args, **kwargs):
        self._pidf = kwargs.get('pidf')
        self._logf = kwargs.get('logf')

    def run(self, *args, **kwargs):
        '''
        called once to kick things off, we'll sleep here and wake up
        periodically to see if there's any work to do
        :return: *never* 
        '''
        self._redis_host = kwargs.get('ip')
        self._redis_port = kwargs.get('port')

        env = dbsetup.determine_environment(None)
        if env == dbsetup.EnvironmentType.DEV:
            schedule_time = _SCHEDULED_TIME_SECONDS_DEV
        else:
            schedule_time = _SCHEDULED_TIME_SECONDS_PROD

        m = "Leaderboard synchronization started, sleep time {} seconds".format(schedule_time)
        logger.info(msg=m)
        pass_number = 1
        while True:
            session = dbsetup.Session()
            try:
                logger.info("Pass #{}".format(pass_number))
                self.perform_task(session)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.exception(msg='failure performing task #{}'.format(pass_number))
            finally:
                pass_number += 1
                session.close()
            time.sleep(schedule_time)

    def perform_task(self, session):
        '''
        here's where we do all the work.
        :param session: 
        :return: 
        '''
        cl = self.read_all_categories(session)
        tm = categorymgr.TallyMan()
        if self._redis_conn is not None:
            tm._redis_host = self._redis_host
            tm._redis_port = self._redis_port
            tm._redis_conn = self._redis_conn

        for c in cl:
            self.scored_photos_by_category(session, tm, c)

    def read_all_categories(self, session):
        '''
        get a complete list of categories no older than 7 days
        exclude "UNKNOWN" (not open yet) and categories that
        are uploading ("UPLOAD")
        :param session: 
        :return: list of categories 
        '''
        earliest_category = datetime.now() + timedelta(days=-7)
        q = session.query(category.Category).filter(category.Category.start_date > earliest_category).\
            filter(category.Category.state != category.CategoryState.UNKNOWN.value).\
            filter(category.Category.state != category.CategoryState.UPLOAD.value)
        return q.all()

    def create_key(self, lb):
        '''
        create_key()
        rank a dummy value to create the category entry properly.
        we'll need to filter this out in the server
        :param lb: leaderboard object
        :return: 
        '''
        lb.rank_member('0', 0, '0')


    def leaderboard_exists(self,session, tm, c):
        '''
        check if the leaderboard already exists. We use a direct
        redis connection and look for the label
        :param session: 
        :param tm: 
        :param c: 
        :return: 
        '''
        if self._redis_conn is None:
            sl = voting.ServerList()
            d = sl.get_redis_server(session)
            if self._redis_host is None:
                self._redis_host = d['ip']

            if self._redis_port is None:
                self._redis_port = d['port']

            self._redis_conn = redis.Redis(host=self._redis_host, port=self._redis_port)
            tm._redis_host = self._redis_host
            tm._redis_port = self._redis_port
            tm._redis_conn = self._redis_conn
            logger.info("Connected to Redis server {0}:{1}".format(tm._redis_host, tm._redis_port))

        self._current_lbname = tm.leaderboard_name(c)
        lb_exists = self._redis_conn.exists(self._current_lbname) == 1
        return lb_exists

    def scored_photos_by_category(self, session, tm, c):
        '''
        if a category doesn't have a leaderboard, we'll read in
        the photos that have scores and rank them in the leaderboard
        :param session: database access
        :param tm: our TallyMan(), our handle to leaderboard functions
        :param c: category we are focused on 
        :return: 
        '''
        # there could be millions of records, so we need to page
        if self.leaderboard_exists(session, tm, c):
            return

        logger.info("processing category {0} \'{1}\'".format(c.id, c.get_description()))
        lb = tm.get_leaderboard_by_category(session, c, check_exist=False)
        self.create_key(lb)

        more_photos = True
        max_pid = 0
        total_records_processed = 0
        while more_photos:
            q = session.query(photo.Photo).filter(photo.Photo.category_id == c.id).\
                filter(photo.Photo.score > 0).\
                filter(photo.Photo.active == 1).\
                filter(photo.Photo.id > max_pid).order_by(photo.Photo.id.asc()).limit(_PAGE_SIZE_PHOTOS)
            pl = q.all()
            more_photos = (len(pl) == _PAGE_SIZE_PHOTOS)
            logger.info("read {} records".format(len(pl)))
            if len(pl) > 0:
                max_pid = pl[-1].id # last element is max photo_id for this pageset
                for p in pl:
                    tm.update_leaderboard(session, c, p, check_exist=False)
                total_records_processed += len(pl)

            time.sleep(_THROTTLE_UPDATES_SECONDS) # brief pause so machine can catch it's breath

        logger.info("...{} total records processed".format(total_records_processed))

# ================================================================================================================

_PIDFILE = '/var/run/synchronize_iiDaemon.pid'
_LOGFILE = '/var/log/synchronize_iiDaemon.log'

def start_daemon():
    dbsetup.metadata.create_all(bind=dbsetup.engine, checkfirst=True)

    redis_host_ip = None
    redis_host_port = None
    for arg in sys.argv:
        kwarg = arg.split('=')
        for k in kwarg:
            if k == 'ip':
                redis_host_ip = kwarg[1]
            if k == 'port':
                redis_host_port = kwarg[1]

    if redis_host_ip is not None:
        logger.info("Redis host IP specified ({0})".format(redis_host_ip))
    if redis_host_port is not None:
        logger.info("Redis host port specified ({0})".format(redis_host_port))

    daemon = sync_daemon(pidf=_PIDFILE, logf=_LOGFILE)
    daemon.run(ip=redis_host_ip, port=redis_host_port)

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

if __name__ == "__main__":
   # with daemon.DaemonContext(pidfile=_PIDFILE, stderr=_LOGFILE, detach_process=True):
    start_daemon()
