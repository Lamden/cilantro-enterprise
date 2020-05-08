from cilantro_ee.crypto.wallet import sign
import time

from contracting.db.encoder import encode
from cilantro_ee.formatting import check_format, rules
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

    assert check_format(payload, rules.TRANSACTION_PAYLOAD_RULES), 'Invalid payload provided!'

    signature = sign(wallet.signing_key(), encode(payload).encode())

    metadata = {
        'signature': signature.hex(),
        'timestamp': int(round(time.time() * 1000))
    }

    tx = {
        'payload': payload,
        'metadata': metadata
    }

    return encode(format_dictionary(tx))
