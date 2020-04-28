from unittest import TestCase
from cilantro.storage.master import CilantroStorageDriver
from cilantro.crypto import wallet


class TestCilantroStorageDriver(TestCase):
    def setUp(self):
        sk, vk = wallet.new()
        self.db = CilantroStorageDriver(key=sk)

    def tearDown(self):
        self.db.drop_collections()

    def test_init(self):
        self.assertIsNotNone(self.db)
