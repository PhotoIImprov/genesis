from enum import Enum
from flask_api import status
import errno


class ErrorTypes(Enum):
    CATEGORY_ERROR = 0x80000000
    USER_ERROR     = 0x81000000
    FRIEND_ERROR   = 0x82000000
    GENERAL_ERROR  = 0x83000000

class iiServerErrors(Enum):

    # first 16 bits are errno value that most closely matches
    # the issue.
    INVALID_CATEGORY    = ErrorTypes.CATEGORY_ERROR.value + errno.EINVAL
    INVALID_USER        = ErrorTypes.USER_ERROR.value     + errno.EINVAL
    INVALID_FRIEND      = ErrorTypes.FRIEND_ERROR.value   + errno.EINVAL
    INVALID_ARGS        = ErrorTypes.GENERAL_ERROR.value  + errno.EINVAL

    @staticmethod
    def error_message(error_code):
        if error_code == iiServerErrors.INVALID_CATEGORY:
            return "invalid category"
        if error_code == iiServerErrors.INVALID_USER:
            return "invalid user"
        if error_code == iiServerErrors.INVALID_FRIEND:
            return "invalid friend"

        return "unknown error"

    @staticmethod
    def http_status(error_code):
        # extract the internal error
        err = error_code.value & 0xFFFF
        if err == errno.EINVAL:
            return status.HTTP_400_BAD_REQUEST

        return status.HTTP_500_INTERNAL_SERVER_ERROR