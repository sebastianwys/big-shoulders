import unittest

import the_loop


class TestSmoke(unittest.TestCase):
    def test_package_imports(self):
        self.assertTrue(the_loop.__version__)


if __name__ == "__main__":
    unittest.main()
