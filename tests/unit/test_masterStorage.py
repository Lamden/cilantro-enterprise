from unittest import TestCase
from cilantro_ee.storage import BlockStorage


class TestMasterStorage(TestCase):
    def setUp(self):
        self.db = BlockStorage()

    def tearDown(self):
        self.db.drop_collections()

    def test_init(self):
        self.assertTrue(self.db)

    def test_q_num(self):
        q = self.db.q(1)

        self.assertEqual(q, {'number': 1})

    def test_q_hash(self):
        q = self.db.q('1')

        self.assertEqual(q, {'hash': '1'})

    def test_put_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

    def test_get_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block(1)

        block.pop('_id')

        self.assertEqual(block, got_block)

    def test_get_block_hash(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block('a')

        block.pop('_id')

        self.assertEqual(block, got_block)

    def test_get_none_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block('b')

        block.pop('_id')

        self.assertIsNone(got_block)

    def test_got_none_block_num(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block(2)

        block.pop('_id')

        self.assertIsNone(got_block)

    def test_drop_collections_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        self.db.drop_collections()

        got_block = self.db.get_block(1)

        block.pop('_id')

        self.assertIsNone(got_block)

    def test_put_other(self):
        index = {
            'hash': 'a',
            'number': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, 999)

        self.assertFalse(_id)

    def test_get_last_n_blocks(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block)

        got_blocks = self.db.get_last_n(3, BlockStorage.BLOCK)

        nums = [b['number'] for b in got_blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_get_last_n_index(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block, BlockStorage.BLOCK)

        got_blocks = self.db.get_last_n(3, BlockStorage.BLOCK)

        nums = [b['number'] for b in got_blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_get_none_from_wrong_n_collection(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block, BlockStorage.BLOCK)

        got_blocks = self.db.get_last_n(3, 5)

        self.assertIsNone(got_blocks)
