from unittest import TestCase
from models import error
from flask_api import status

class TestError(TestCase):
    def test_error_message(self):
        msg = error.iiServerErrors.error_message((error.iiServerErrors.INVALID_ARGS))
        assert(msg == "unknown error")

        msg = error.iiServerErrors.error_message((error.iiServerErrors.NOTUPLOAD_CATEGORY))
        assert(msg == "category specified is not accepting uploads")

        msg = error.iiServerErrors.error_message((error.iiServerErrors.INVALID_FRIEND))
        assert (msg == "invalid friend")

        msg = error.iiServerErrors.error_message((error.iiServerErrors.INVALID_USER))
        assert (msg == "invalid user")

        msg = error.iiServerErrors.error_message((error.iiServerErrors.NOTVOTING_CATEGORY))
        assert (msg == "category is not accepting votes")

        msg = error.iiServerErrors.error_message((error.iiServerErrors.INVALID_CATEGORY))
        assert (msg == "invalid category")


    def test_http_status(self):
        code = error.iiServerErrors.http_status(error.iiServerErrors.INVALID_CATEGORY)
        assert(code == status.HTTP_400_BAD_REQUEST)

        code = error.iiServerErrors.http_status(error.iiServerErrors.INVALID_USER)
        assert (code == status.HTTP_400_BAD_REQUEST)

        code = error.iiServerErrors.http_status(error.iiServerErrors.INVALID_FRIEND)
        assert (code == status.HTTP_400_BAD_REQUEST)

        code = error.iiServerErrors.http_status(error.iiServerErrors.INVALID_ARGS)
        assert (code == status.HTTP_400_BAD_REQUEST)

        code = error.iiServerErrors.http_status(error.iiServerErrors.NOTVOTING_CATEGORY)
        assert (code == status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_error_string(self):
        e = error.error_string('invalidkey')
        assert(e == error.d_ERROR_STRINGS['UNKNOWN_ERROR'])
