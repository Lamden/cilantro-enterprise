from unittest import TestCase
from cilantro_ee.nodes.masternode.server import validator
from cilantro_ee.crypto.json_transaction import build_transaction
from cilantro_ee.crypto.wallet import Wallet, _verify
from contracting.db.encoder import encode, decode
from cilantro_ee.storage import BlockchainDriver


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
    def setUp(self):
        self.driver = BlockchainDriver()
        self.driver.flush()

    def test_check_tx_formatting_succeeds(self):
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

        error = validator.check_tx_formatting(decoded, 'b' * 64)
        self.assertIsNone(error)

    def test_check_tx_formatting_not_formatted_fails(self):
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
        decoded['payload']['nonce'] = -123

        error = validator.check_tx_formatting(decoded, 'b' * 64)

        self.assertEqual(error, validator.TransactionFormattingError)

    def test_check_tx_formatting_incorrect_processor_fails(self):
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

        error = validator.check_tx_formatting(decoded, 'c' * 64)

        self.assertEqual(error, validator.TransactionProcessorInvalid)

    def test_check_tx_formatting_signature_fails(self):
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
        decoded['payload']['sender'] = 'a' * 64

        error = validator.check_tx_formatting(decoded, 'b' * 64)

        self.assertEqual(error, validator.TransactionSignatureInvalid)

    def test_get_nonces_when_none_exist_return_zeros(self):
        n, p = validator.get_nonces('a' * 64, 'b' * 64, self.driver)
        self.assertEqual(n, 0)
        self.assertEqual(p, 0)

    def test_get_nonces_correct_when_exist(self):
        sender = b'a' * 32
        processor = b'b' * 32

        self.driver.set_pending_nonce(
            sender=sender,
            processor=processor,
            nonce=5
        )

        self.driver.set_nonce(
            sender=sender,
            processor=processor,
            nonce=3
        )

        n, p = validator.get_nonces(
            sender=sender.hex(),
            processor=processor.hex(),
            driver=self.driver
        )
        self.assertEqual(n, 3)
        self.assertEqual(p, 5)

    def test_get_pending_nonce_if_strict_increments(self):
        new_pending_nonce = validator.get_new_pending_nonce(
            tx_nonce=2,
            nonce=1,
            pending_nonce=2
        )

        self.assertEqual(new_pending_nonce, 3)

    def test_get_pending_nonce_if_not_strict_is_highest_nonce(self):
        new_pending_nonce = validator.get_new_pending_nonce(
            tx_nonce=3,
            nonce=1,
            pending_nonce=2,
            strict=False
        )

        self.assertEqual(new_pending_nonce, 4)

    def test_get_pending_nonce_if_strict_invalid(self):
        with self.assertRaises(validator.TransactionNonceInvalid):
             validator.get_new_pending_nonce(
                tx_nonce=3,
                nonce=1,
                pending_nonce=2
            )

    def test_get_pending_nonce_if_not_strict_invalid(self):
        with self.assertRaises(validator.TransactionNonceInvalid):
             validator.get_new_pending_nonce(
                tx_nonce=1,
                nonce=1,
                pending_nonce=2,
                strict=False
            )

    def test_get_pending_nonce_too_many_tx_per_block_raise_error(self):
        with self.assertRaises(validator.TransactionTooManyPendingException):
            validator.get_new_pending_nonce(
                tx_nonce=16,
                nonce=0,
                pending_nonce=0
            )

    def test_get_pending_nonce_too_many_tx_per_block_raise_error_pending(self):
        with self.assertRaises(validator.TransactionTooManyPendingException):
            validator.get_new_pending_nonce(
                tx_nonce=17,
                nonce=0,
                pending_nonce=1
            )

    def test_has_enough_stamps_passes(self):
        validator.has_enough_stamps(
            balance=10,
            stamp_per_balance=10000,
            stamps_supplied=1000,
        )

    def test_has_enough_stamps_fails(self):
        with self.assertRaises(validator.TransactionSenderTooFewStamps):
            validator.has_enough_stamps(
                balance=10,
                stamp_per_balance=10000,
                stamps_supplied=100001,
            )

    def test_has_enough_stamps_fails_minimum_stamps(self):
        with self.assertRaises(validator.TransactionSenderTooFewStamps):
            validator.has_enough_stamps(
                balance=10,
                stamp_per_balance=10000,
                stamps_supplied=100000,
                contract='currency',
                function='transfer',
                amount=10
            )

    def test_contract_is_valid_passes(self):
        validator.contract_name_is_valid(
            contract='submission',
            function='submit_contract',
            name='con_hello'
        )

    def test_contract_fails(self):
        with self.assertRaises(validator.TransactionContractNameInvalid):
            validator.contract_name_is_valid(
                contract='submission',
                function='submit_contract',
                name='co_hello'
            )