
import unittest

from datetime import datetime, timedelta
from naas.library.auth import tacacs_auth_lockout
from pickle import dumps
from redis import Redis


class TestAuthLockout(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        """
        Setup our self objects for this test case
        """
        super().__init__(*args, **kwargs)

        self.username = "brett"
        self.redis = Redis()
        self.sample_fail_dict = {"failure_count": 0, "failure_timestamps": bytes()}

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

        # Test "old" failures by stashing a 9 failures from _before_ ten minutes ago.
        self.stash_failures(failure_count=9, old=True)

        # Test if 9 existing failures from greater than 10 minutes ago:
        with self.subTest(msg="Checking failures, 9 reported > 10 minutes ago."):
            self.assertEqual(tacacs_auth_lockout(username=self.username), False)

        # Test if 9 existing failures from greater than 10 minutes ago, and we're reporting a new failure:
        with self.subTest(msg="Checking failures, 9 reported > 10 minutes ago, reporting 1 new failure."):
            self.assertEqual(tacacs_auth_lockout(username=self.username, report_failure=True), False)

        # Now add 9 new failures
        for _ in range(9):
            tacacs_auth_lockout(username=self.username, report_failure=True)

        # Finally test that these failures "count" and we're locked out:
        with self.subTest(msg="Testing lockout after removing old faiulres, but new came in."):
            self.assertEqual(tacacs_auth_lockout(username=self.username, report_failure=True), True)

    def tearDown(self) -> None:
        """
        Delete our test entry in Redis
        :return:
        """

        self.redis.delete("naas_failures_brett")

    def stash_failures(self, failure_count: int, old: bool) -> None:
        """
        Will clear the test DB entry, and stash the given number of failures.  Can also be _OLDER_ than 10 minutes
        :param failure_count: How many failures are we stashing
        :param old: Are we stashing failures from prior to 10 minutes ago?
        :return:
        """

        # Clear out all the failures from previous tests
        self.redis.delete("naas_failures_brett")

        self.sample_fail_dict["failure_count"] = failure_count
        fail_timestamps = []
        for _ in range(failure_count):
            # Add the failures into the list
            fail_time = datetime.now()
            if old:
                fail_time = fail_time - timedelta(minutes=30)
            fail_timestamps.append(fail_time)
        self.sample_fail_dict["failure_timestamps"] = dumps(fail_timestamps)

        self.redis.hmset("naas_failures_brett", self.sample_fail_dict)
