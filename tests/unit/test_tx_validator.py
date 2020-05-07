from unittest import TestCase
from cilantro_ee.nodes.masternode.server import validator
from cilantro_ee.crypto.json_transaction import build_transaction
from cilantro_ee.crypto.wallet import Wallet, _verify
from contracting.db.encoder import encode, decode


class TestTransactionBuilder(TestCase):
    def test_init_valid_doesnt_assert(self):
        build_transaction(
            wallet=Wallet(),
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

    def test_init_invalid_format_raises_assert(self):
        with self.assertRaises(AssertionError):
            build_transaction(
                wallet=Wallet(),
                processor='b' * 65,
                stamps=123,
                nonce=0,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 123,
                    'to': 'jeff'
                }
            )

    def test_sign_works_properly(self):
        w = Wallet()

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        res = _verify(
            w.verifying_key(),
            encode(decoded['payload']).encode(),
            bytes.fromhex(decoded['metadata']['signature'])
        )

        self.assertTrue(res)

    def test_serialize_works_properly(self):
        w = Wallet()

        expected = {
                'sender': w.verifying_key().hex(),
                'processor': 'b' * 64,
                'stamps_supplied': 123,
                'nonce': 0,
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': 123,
                    'to': 'jeff'
                }
            }

        tx = build_transaction(
            wallet=w,
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        decoded = decode(tx)

        self.assertDictEqual(decoded['payload'], expected)


class TestValidator(TestCase):
    def test_check_tx_formatting_succeeds(self):
        pass