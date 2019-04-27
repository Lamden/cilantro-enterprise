from cilantro_ee.messages.block_data.notification import BlockNotification
from unittest import TestCase
from unittest.mock import MagicMock, patch


class TestBlockNotification(TestCase):

    def test_create(self):
        prev_hash = 'A' * 64
        block_hash = 'X3' * 32
        block_num = 32
        block_owners = [ "abc", "def", "pqr"]
        input_hashes = [{'AB' * 32, 'BC' * 32}, {'C'*64, 'D'*64}, set(), {'E'*64}]

        fbn = BlockNotification.create(prev_block_hash=prev_hash, block_hash=block_hash, block_num=block_num,
                                       block_owners=block_owners, input_hashes=input_hashes)

        self.assertEqual(fbn.prev_block_hash, prev_hash)
        self.assertEqual(fbn.input_hashes, input_hashes)

    def test_serialize_deserialize(self):
        prev_hash = 'A' * 64
        block_hash = 'X3' * 32
        block_num = 32
        block_owners = [ "abc", "def", "pqr"]
        input_hashes = [{'AB' * 32, 'BC' * 32}, {'C'*64, 'D'*64}, set(), {'E'*64}]

        fbn = BlockNotification.create(prev_block_hash=prev_hash, block_hash=block_hash, block_num=block_num,
                                       block_owners=block_owners, input_hashes=input_hashes)
        clone = FailedBlockNotification.from_bytes(fbn.serialize())

        self.assertEqual(fbn, clone)
