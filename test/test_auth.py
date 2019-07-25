
import unittest

from naas.library.auth import tacacs_auth_lockout
from redis import Redis


class TestAuthLockout(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        """
        Setup our self objects for this test case
        """
        super().__init__(*args, **kwargs)

        self.username = "brett"
        self.redis = Redis()

    def setUp(self) -> None:
        """
        Plumb up our values in redis, ensure Redis is good, etc.
        :return:
        """
        self.redis.delete("naas_failures_brett")

    def test_tacacs_auth_lockout(self):
        """
        Tests for the tacacs_auth_lockout function
        :return:
        """

        # Test if no existing failures in cache, and we're not reporting one
        with self.subTest(msg="Checking failures, none yet reported for user."):
            self.assertEqual(tacacs_auth_lockout(username=self.username), False)

        # Test if no existing failures in cache, and we _ARE_ reporting one
        with self.subTest(msg="Reporting first failure for user."):
            self.assertEqual(tacacs_auth_lockout(username=self.username, report_failure=True), False)

        # Iterate up to 9 failures:
        for _ in range(8):
            tacacs_auth_lockout(username=self.username, report_failure=True)

        # Test if 9 existing failures and checking (But not adding new failure)
        with self.subTest(msg="Checking failures, 9 reported so far for user."):
            self.assertEqual(tacacs_auth_lockout(username=self.username), False)

        # Test if 9 existing failures and we report the tenth
        with self.subTest(msg="Checking failures, 9 reported, reporting 1 more."):
            self.assertEqual(tacacs_auth_lockout(username=self.username, report_failure=True), True)

        # Test if 10 failures and we are simply checking
        with self.subTest(msg="Checking failures, 10 reported so far for user."):
            self.assertEqual(tacacs_auth_lockout(username=self.username), True)

        # Test if 10 failures and we try to report another
        with self.subTest(msg="Checking failures, 10 reported so far for user, trying to report another failure."):
            self.assertEqual(tacacs_auth_lockout(username=self.username, report_failure=True), True)

    def tearDown(self) -> None:
        """
        Delete our test entry in Redis
        :return:
        """

        self.redis.delete("naas_failures_brett")
