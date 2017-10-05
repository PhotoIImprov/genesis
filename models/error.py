from enum import Enum
from flask_api import status
import errno

class ErrorTypes(Enum):
    CATEGORY_ERROR = 0x80000000
    USER_ERROR     = 0x81000000
    FRIEND_ERROR   = 0x82000000
    GENERAL_ERROR  = 0x83000000
    PHOTO_ERROR    = 0x84000000
    CATEGORY_SUCCESS = 0x4000000

class iiServerErrors(Enum):

    # first 16 bits are errno value that most closely matches
    # the issue.
    INVALID_CATEGORY    = ErrorTypes.CATEGORY_ERROR.value + errno.EINVAL
    INVALID_USER        = ErrorTypes.USER_ERROR.value     + errno.EINVAL
    INVALID_FRIEND      = ErrorTypes.FRIEND_ERROR.value   + errno.EINVAL
    INVALID_ARGS        = ErrorTypes.GENERAL_ERROR.value  + errno.EINVAL
    NOTUPLOAD_CATEGORY  = ErrorTypes.PHOTO_ERROR.value    + errno.EINVAL
    NOTVOTING_CATEGORY  = ErrorTypes.CATEGORY_ERROR.value + errno.ECANCELED
    NO_STATE_CHANGE     = ErrorTypes.CATEGORY_SUCCESS.value


    @staticmethod
    def error_message(error_code):
        if error_code == iiServerErrors.INVALID_CATEGORY:
            return "invalid category"
        if error_code == iiServerErrors.INVALID_USER:
            return "invalid user"
        if error_code == iiServerErrors.INVALID_FRIEND:
            return "invalid friend"
        if error_code == iiServerErrors.NOTUPLOAD_CATEGORY:
            return "category specified is not accepting uploads"
        if error_code == iiServerErrors.NO_STATE_CHANGE:
            return "category is already in proposed state"
        if error_code == iiServerErrors.NOTVOTING_CATEGORY:
            return "category is not accepting votes"

        return "unknown error"

    @staticmethod
    def http_status(error_code):
        # extract the internal error
        err = error_code.value & 0xFFFF
        if err == errno.EINVAL:
            return status.HTTP_400_BAD_REQUEST
        if error_code == iiServerErrors.NO_STATE_CHANGE:
            return status.HTTP_200_OK

        return status.HTTP_500_INTERNAL_SERVER_ERROR

d_ERROR_STRINGS = {'NO_JSON': "missing JSON data",
                   'NO_ARGS': "missing querystring arguments",
                   'MISSING_ARGS' : "missing one or more required arguments",
                   'FRIENDSHIP_UPDATED': "friendship updated",
                   'NO_USER': "missing user id",
                   'PHOTO_UPLOADED': "photo uploaded",
                   'NO_SUCH_USER': "no such user",
                   'TOO_MANY_BALLOTS': "too many ballots (4 or less please)",
                   'NO_BALLOT': "no ballot created",
                   'MISSING_CATEGORY': "missing category id",
                   'CATEGORY_ERROR': "error fetching category",
                   'FRIEND_REQ_ERROR': "problem creating the friend request",
                   'ANON_USER_ERROR': "error creating anonymous user",
                   'USER_ALREADY_EXISTS': "user already exists!",
                   'ANON_ALREADY_EXISTS': "anonymous user already exists",
                   'USER_CREATE_ERROR': "error creating user",
                   'ACCOUNT_CREATED': "account created",
                   'THANK_YOU_VOTING': "thank you for voting",
                   'WILL_NOTIFY_FRIEND': "thank you, will notify your friend",
                   'CATEGORY_STATE': "category state updated",
                   'NO_LEADERBOARD': "failed to get leaderboard",
                   'NO_PHOTO': "no photo read",
                   'ERROR_PHOTO': "error accessing photo file",
                   'NO_SUBMISSION': "no submission read",
                   'TABULATE_ERROR': "error tabulating ballot",
                   'UPLOAD_ERROR': "error uploading photo",
                   'NO_SUCH_FRIEND': "friend request not found or error",
                   'NOT_IMPLEMENTED': "service has not been implemented yet.",
                   'EMAIL_NOT_FOUND': "email address not found.",
                   'RESTRICTED_API' : "this API is restricted to authorized staff only",
                   'BAD_DATEFORMAT' : "improperly formatted date string, should be YYYY-mm-dd HH:MM",
                   'TOO_EARLY': "date specified is too early",
                   'BAD_ARGS': "one or more arguments are in error",
                   'NO_CATEGORY': "no category available for operation",

                   # this is if we don't map to anything
                   'UNKNOWN_ERROR': "unknown error ??"}

def error_string(key):
    try:
        value = d_ERROR_STRINGS[key]
    except:
        value = d_ERROR_STRINGS['UNKNOWN_ERROR']
    finally:
        return str(value)
