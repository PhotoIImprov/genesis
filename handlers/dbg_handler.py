import logging
import traceback

'''
    DebugHandler()
    special handler that writes the error to a local variable for debugging purposes only!
'''

class DebugHandler(logging.Handler):
    _dbg_log = None
    def emit(self, record):
        trace = None
        exc = record.__dict__['exc_info']
        if exc:
            trace = traceback.format_exc()
        log = {'logger':record.__dict__['name'],
                  'level':record.__dict__['levelname'],
                  'trace':trace,
                  'msg':record.__dict__['msg']}

        try:
            self._dbg_log = log
        except:
            self._dbg_log = None

        assert(self._dbg_log is not None)