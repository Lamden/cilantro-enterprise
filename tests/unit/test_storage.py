from cilantro_ee import storage
from contracting.db.driver import ContractDriver
from unittest import TestCase


class TestNonce(TestCase):
    def setUp(self):
        self.nonces = storage.NonceStorage()
        self.nonces.flush()

    def tearDown(self):
        self.nonces.flush()

    def test_get_nonce_none_if_not_set_first(self):
        n = self.nonces.get_nonce(
            sender='test',
            processor='test2'
        )

        self.assertIsNone(n)

    def test_get_pending_nonce_none_if_not_set_first(self):
        n = self.nonces.get_pending_nonce(
            sender='test',
            processor='test2'
        )

        self.assertIsNone(n)

    def test_set_then_get_nonce_returns_set_nonce(self):
        self.nonces.set_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_set_then_get_pending_nonce_returns_set_pending_nonce(self):
        self.nonces.set_pending_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_pending_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_get_latest_nonce_zero_if_none_set(self):
        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 0)

    def test_get_latest_nonce_returns_pending_nonce_if_not_none(self):
        self.nonces.set_pending_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_get_latest_nonce_nonce_if_pending_nonce_is_none(self):
        self.nonces.set_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)


class TestStorage(TestCase):
    def setUp(self):
        self.driver = ContractDriver()
        self.driver.flush()

    def tearDown(self):
        self.driver.flush()

    def test_get_latest_block_hash_0s_if_none(self):
        h = storage.get_latest_block_hash(self.driver)
        self.assertEqual(h, '0' * 64)

    def test_get_latest_block_hash_correct_after_set(self):
        storage.set_latest_block_hash('a' * 64, self.driver)
        h = storage.get_latest_block_hash(self.driver)
        self.assertEqual(h, 'a' * 64)

    def test_get_latest_block_height_0_if_none(self):
        h = storage.get_latest_block_height(self.driver)
        self.assertEqual(h, 0)

    def test_get_latest_block_height_correct_after_set(self):
        storage.set_latest_block_height(123, self.driver)
        h = storage.get_latest_block_height(self.driver)
        self.assertEqual(h, 123)


tx_1 = {
    'transaction': {
        'payload': {
            'sender': 'abc',
            'processor': 'def',
            'nonce': 123,
        }
    },
    'state': [
        {
            'key': 'hello', 'value': 'there'
        },
        {
            'key': 'name', 'value': 'jeff'
        }
    ]
}

tx_2 = {
    'transaction': {
        'payload': {
            'sender': 'abc',
            'processor': 'def',
            'nonce': 124,
        }
    },
    'state': [
        {
            'key': 'hello', 'value': 'there2'
        },
        {
            'key': 'name2', 'value': 'jeff2'
        }
    ]
}

tx_3 = {
    'transaction': {
        'payload': {
            'sender': 'xxx',
            'processor': 'yyy',
            'nonce': 42,
        }
    },
    'state': [
        {
            'key': 'another', 'value': 'value'
        },
        {
            'key': 'something', 'value': 'else'
        }
    ]
}


block = {
    'hash': 'f' * 64,
    'number': 555,
    'subblocks': [
        {
            'transactions': [tx_1, tx_2]
        },
        {
            'transactions': [tx_3]
        }
    ]
}


class TestUpdatingState(TestCase):
    def setUp(self):
        self.driver = ContractDriver()
        self.nonces = storage.NonceStorage()
        self.nonces.flush()
        self.driver.flush()
        self.driver.clear_pending_state()

    def tearDown(self):
        self.nonces.flush()
        self.driver.flush()
        self.driver.clear_pending_state()

    def test_state_updated_to_correct_values_in_tx(self):
        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        self.assertIsNone(v1)
        self.assertIsNone(v2)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        self.assertEqual(v1, 'there')
        self.assertEqual(v2, 'jeff')

    def test_nonces_set_to_tx_value(self):
        n = self.nonces.get_latest_nonce(sender='abc', processor='def')
        self.assertEqual(n, 0)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        n = self.nonces.get_latest_nonce(sender='abc', processor='def')
        self.assertEqual(n, 123)

    def test_nonces_deleted_after_all_updates(self):
        self.nonces.set_pending_nonce(
            sender='abc',
            processor='def',
            value=122
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')

        self.assertEqual(n, 122)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')

        self.assertEqual(n, None)

    def test_multiple_txs_deletes_multiple_nonces(self):
        self.nonces.set_pending_nonce(
            sender='abc',
            processor='def',
            value=122
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')
        self.assertEqual(n, 122)

        self.nonces.set_pending_nonce(
            sender='xxx',
            processor='yyy',
            value=4
        )

        n = self.nonces.get_pending_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, 4)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        storage.update_state_with_transaction(
            tx=tx_2,
            driver=self.driver,
            nonces=self.nonces
        )

        storage.update_state_with_transaction(
            tx=tx_3,
            driver=self.driver,
            nonces=self.nonces
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')
        self.assertEqual(n, None)

        n = self.nonces.get_pending_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, None)

        n = self.nonces.get_latest_nonce(sender='abc', processor='def')
        self.assertEqual(n, 124)

        n = self.nonces.get_latest_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, 42)

    def test_multiple_tx_state_updates_correctly(self):
        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        v3 = self.driver.get('name2', mark=False)

        v4 = self.driver.get('another', mark=False)
        v5 = self.driver.get('something', mark=False)

        self.assertIsNone(v1)
        self.assertIsNone(v2)
        self.assertIsNone(v3)
        self.assertIsNone(v4)
        self.assertIsNone(v5)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        storage.update_state_with_transaction(
            tx=tx_2,
            driver=self.driver,
            nonces=self.nonces
        )

        storage.update_state_with_transaction(
            tx=tx_3,
            driver=self.driver,
            nonces=self.nonces
        )

        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        v3 = self.driver.get('name2', mark=False)

        v4 = self.driver.get('another', mark=False)
        v5 = self.driver.get('something', mark=False)

        self.assertEqual(v1, 'there2')
        self.assertEqual(v2, 'jeff')
        self.assertEqual(v3, 'jeff2')
        self.assertEqual(v4, 'value')
        self.assertEqual(v5, 'else')

    def test_update_with_block_sets_hash_and_height(self):
        _hash = storage.get_latest_block_hash(self.driver)
        num = storage.get_latest_block_height(self.driver)

        self.assertEqual(_hash, '0' * 64)
        self.assertEqual(num, 0)

        storage.update_state_with_block(
            block=block,
            driver=self.driver,
            nonces=self.nonces
        )

        _hash = storage.get_latest_block_hash(self.driver)
        num = storage.get_latest_block_height(self.driver)

        self.assertEqual(_hash, 'f' * 64)
        self.assertEqual(num, 555)

    def test_update_with_block_sets_nonces_correctly(self):
        self.nonces.set_pending_nonce(
            sender='abc',
            processor='def',
            value=122
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')
        self.assertEqual(n, 122)

        self.nonces.set_pending_nonce(
            sender='xxx',
            processor='yyy',
            value=4
        )

        n = self.nonces.get_pending_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, 4)

        storage.update_state_with_block(
            block=block,
            driver=self.driver,
            nonces=self.nonces
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')
        self.assertEqual(n, None)

        n = self.nonces.get_pending_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, None)

        n = self.nonces.get_latest_nonce(sender='abc', processor='def')
        self.assertEqual(n, 124)

        n = self.nonces.get_latest_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, 42)

    def test_update_state_with_block_sets_state_correctly(self):
        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        v3 = self.driver.get('name2', mark=False)

        v4 = self.driver.get('another', mark=False)
        v5 = self.driver.get('something', mark=False)

        self.assertIsNone(v1)
        self.assertIsNone(v2)
        self.assertIsNone(v3)
        self.assertIsNone(v4)
        self.assertIsNone(v5)

        storage.update_state_with_block(
            block=block,
            driver=self.driver,
            nonces=self.nonces
        )

        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        v3 = self.driver.get('name2', mark=False)

        v4 = self.driver.get('another', mark=False)
        v5 = self.driver.get('something', mark=False)

        self.assertEqual(v1, 'there2')
        self.assertEqual(v2, 'jeff')
        self.assertEqual(v3, 'jeff2')
        self.assertEqual(v4, 'value')
        self.assertEqual(v5, 'else')