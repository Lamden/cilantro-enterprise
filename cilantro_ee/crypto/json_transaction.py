from cilantro_ee.crypto.wallet import _sign
import time

from contracting.db.encoder import encode
from cilantro_ee.messages.formatting.transactions import transaction_payload_is_formatted
from cilantro_ee.crypto.canonical import format_dictionary


def build_transaction(wallet, contract: str, function: str, kwargs: dict, nonce: int, processor: str, stamps: int):
    payload = {
        'contract': contract,
        'function': function,
        'kwargs': kwargs,
        'nonce': nonce,
        'processor': processor,
        'sender': wallet.verifying_key().hex(),
        'stamps_supplied': stamps,
    }

    assert transaction_payload_is_formatted(payload), 'Invalid payload provided!'

    signature = _sign(wallet.signing_key(), encode(payload).encode())

    metadata = {
        'signature': signature.hex(),
        'timestamp': int(round(time.time() * 1000))
    }

    tx = {
        'payload': payload,
        'metadata': metadata
    }

    return encode(format_dictionary(tx))
