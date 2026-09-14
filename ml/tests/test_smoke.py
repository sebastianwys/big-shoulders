import unittest

import big_shoulders


class TestSmoke(unittest.TestCase):
    def test_package_imports(self):
        self.assertTrue(big_shoulders.__version__)


if __name__ == "__main__":
    unittest.main()
