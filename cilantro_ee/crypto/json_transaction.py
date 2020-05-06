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





