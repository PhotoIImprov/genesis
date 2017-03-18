from unittest import TestCase
from models import error
from flask_api import status

class TestError(TestCase):
    def test_error_message(self):
        msg = error.iiServerErrors.error_message((error.iiServerErrors.INVALID_ARGS))
        assert(msg == "unknown error")

    def test_http_status(self):
        code = error.iiServerErrors.http_status(error.iiServerErrors.INVALID_CATEGORY)
        assert(code == status.HTTP_400_BAD_REQUEST)

        code = error.iiServerErrors.http_status(error.iiServerErrors.INVALID_USER)
        assert (code == status.HTTP_400_BAD_REQUEST)

        code = error.iiServerErrors.http_status(error.iiServerErrors.INVALID_FRIEND)
        assert (code == status.HTTP_400_BAD_REQUEST)

        code = error.iiServerErrors.http_status(error.iiServerErrors.INVALID_ARGS)
        assert (code == status.HTTP_400_BAD_REQUEST)

