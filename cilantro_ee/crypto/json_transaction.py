from cilantro_ee.crypto import wallet
from cilantro_ee.storage import BlockchainDriver
import time
import os

from contracting.db.encoder import encode, decode
from cilantro_ee.messages.formatting.transactions import transaction_is_formatted
from cilantro_ee.messages.formatting.primatives import contract_name_is_formatted
from cilantro_ee.crypto.canonical import format_dictionary


class TransactionBuilder:
    def __init__(self, sender, contract: str, function: str, kwargs: dict, stamps: int, processor: bytes, nonce: int):
        self.payload = {
            'contract': contract,
            'function': function,
            'kwargs': kwargs,
            'nonce': nonce,
            'processor': processor,
            'sender': sender,
            'stamps_supplied': stamps,
        }

        self.metadata = {
            'signature': None,
            'timestamp': None
        }

        self.transaction = {
            'metadata': self.metadata,
            'payload': self.payload
        }

        self.transaction = format_dictionary(self.transaction)

        assert transaction_is_formatted, 'Transaction not formatted correctly!'

    def sign(self, signing_key: bytes):
        signature = wallet._sign(signing_key, encode(self.payload))
        self.metadata['signature'] = signature

    def serialize(self):
        assert self.metadata['signature'] is not None, 'Sign tx first'

        self.metadata['timestamp'] = int(round(time.time() * 1000))

        return encode(self.transaction)


class TransactionException(Exception):
    pass


class TransactionSignatureInvalid(TransactionException):
    pass


class TransactionPOWProofInvalid(TransactionException):
    pass


class TransactionProcessorInvalid(TransactionException):
    pass


class TransactionTooManyPendingException(TransactionException):
    pass


class TransactionNonceInvalid(TransactionException):
    pass


class TransactionStampsNegative(TransactionException):
    pass


class TransactionSenderTooFewStamps(TransactionException):
    pass


class TransactionContractNameInvalid(TransactionException):
    pass


def nonce_is_valid(tx_nonce, nonce, pending_nonce, strict=True, tx_per_block=15):
    # Attempt to get the current block's pending nonce
    if tx_nonce - nonce > tx_per_block or pending_nonce - nonce >= tx_per_block:
        raise TransactionTooManyPendingException

    # Strict mode requires exact sequence matching (1, 2, 3, 4). This is for masternodes
    if strict:
        if tx_nonce != pending_nonce:
            raise TransactionNonceInvalid
        pending_nonce += 1

    # However, some of those tx's might fail verification and never make it to delegates. Thus,
    # delegates shouldn't be as concerned. (1, 2, 4) should be valid for delegates.
    else:
        if tx_nonce < pending_nonce:
            raise TransactionNonceInvalid
        pending_nonce = tx_nonce + 1

    return pending_nonce


def has_enough_stamps(balance, stamp_cost, stamps_supplied, contract, function, amount):
    if balance * stamp_cost < stamps_supplied:
        raise TransactionSenderTooFewStamps

    # Prevent people from sending their entire balances for free by checking if that is what they are doing.
    if contract == 'currency' and function == 'transfer':

        # If you have less than 2 transactions worth of tau after trying to send your amount, fail.
        if ((balance - amount) * stamp_cost) / 3000 < 2:
            raise TransactionSenderTooFewStamps


def contract_name_is_valid(contract, function, name):
    if contract == 'submission' and function == 'submit_contract' and not contract_name_is_formatted(name):
        raise TransactionContractNameInvalid


def transaction_is_valid(transaction: bytes,
                         expected_processor: str,
                         driver: BlockchainDriver,
                         strict=True,
                         tx_per_block=15):
    # Validate Signature
    tx = decode(transaction)

    if not wallet._verify(
            tx['payload']['sender'],
            encode(tx['payload']['payload']),
            tx['metadata']['signature']
    ):
        raise TransactionSignatureInvalid

    # Check nonce processor is correct
    if tx['payload']['processor'] != expected_processor:
        raise TransactionProcessorInvalid

    # Validate Stamps
    if tx['payload']['stamps_supplied'] < 0:
        raise TransactionStampsNegative


    driver.set_pending_nonce(tx['payload']['processor'], tx['payload']['sender'], pending_nonce)
