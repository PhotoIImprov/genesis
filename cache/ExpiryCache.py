"""
Basic expiry cache implementation python.
"""

import time
import threading

SCHEDULE_TIMEOUT = 59

"""
Usage:

from cache import ExpiryCache
c = ExpiryCache()

# Insert into cache
c.put("name", "ExpiryCache")
c.put("name", "ExpiryCache", 60) # with ttl

# Get value
c.get("name")

"""


class ExpiryValueException(Exception):
    pass


class ExpiryCacheObject(object):
    """
    ExpiryCache object: Contains basic cached object information.

    @key: Key to be stored in cache.
    @value: Value to stored per key.
    @ttl: Time to live in secs
    """

    def __init__(self, key: str, value: object, ttl=None) -> None:
        self.key = key
        self.value = value
        self.ttl = ttl
        self.timeout = time.time()


class ExpiryCache(object):
    """
    Main cache handler, responsible for caching and
    exposes get and put api.

    Main cache data structure used is python  dict
    """

    def __init__(self, *args, **kwargs):
        self._cache = {}
        self.lock = threading.RLock()
        self.schedule_cleaner()

    def is_expired(self, obj: object) -> bool:
        """
        Checks if cached object has expired.
        If yes, remove it from cache.
        """

        with self.lock:
            if obj.ttl is None:
                return False

            if time.time() > obj.ttl + obj.timeout:
                self._cache.pop(obj.key)
                return True
            return False

    def schedule_cleaner(self) -> None:
        t = threading.Timer(SCHEDULE_TIMEOUT, self.timely_cache_cleaner)
        t.setDaemon(True)
        t.start()

    def expire_key(self, key: str) -> None:
        with self.lock:
            obj = self._cache.pop(key)

    def timely_cache_cleaner(self) -> None:
        """
        Timely checks for expired object in cache and
        clears object from cache.
        """

        with self.lock:
            all_obj = self._cache.values()

            for obj in all_obj:
                self.is_expired(obj)
            self.schedule_cleaner()

    def put(self, key: str, value: object, ttl=None) -> None:
        """
        Insert value in cache
        """

        with self.lock:
            if ttl is not None and type(ttl) not in [int, float]:
                raise ExpiryValueException("ttl should be int or float.")

            self._cache[key] = ExpiryCacheObject(key, value, ttl)

    def get(self, key: str) -> object:
        """
        Retrive value from cache.
        """

        with self.lock:
            obj = self._cache.get(key)
            if obj is None:
                return None

            if self.is_expired(obj):
                return None

            return obj.value

# instantiate a "global" instance of our cache
_expiry_cache = ExpiryCache()

