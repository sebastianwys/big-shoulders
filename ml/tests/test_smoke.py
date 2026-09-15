import unittest

import loop


class TestSmoke(unittest.TestCase):
    def test_package_imports(self):
        self.assertTrue(loop.__version__)


if __name__ == "__main__":
    unittest.main()
