from cilantro_ee.formatting.primatives import *

TRANSACTION_PAYLOAD_RULES = {
    'sender': vk_is_formatted,
    'processor': vk_is_formatted,
    'nonce': number_is_formatted,
    'stamps_supplied': number_is_formatted,
    'contract': identifier_is_formatted,
    'function': identifier_is_formatted,
    'kwargs': kwargs_are_formatted
}

TRANSACTION_METADATA_RULES = {
    'signature': signature_is_formatted,
    'timestamp': number_is_formatted
}

TRANSACTION_RULES = {
    'metadata': TRANSACTION_METADATA_RULES,
    'payload': TRANSACTION_PAYLOAD_RULES
}

TRANSACTION_OUTPUT_RULES = {
    'hash': vk_is_formatted,
    'result': is_string,
    'stamps_used': number_is_formatted,
    'state': kwargs_are_formatted,
    'status': number_is_formatted,
    'transaction': TRANSACTION_RULES,
}
