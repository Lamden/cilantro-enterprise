from .primatives import *


def transaction_payload_is_valid(t: dict):
    expected_keys = {'sender', 'processor', 'nonce', 'stamps_supplied', 'contract', 'function', 'kwargs'}

    if not dict_has_keys(t, expected_keys):
        return False

    if not vk_is_valid(t['sender']):
        return False

    if not vk_is_valid(t['processor']):
        return False

    if not number_is_valid(t['nonce']):
        return False

    if not number_is_valid(t['stamps_supplied']):
        return False

    if not contract_name_is_valid(t['contract']):
        return False

    if not identifier_is_valid(t['function']):
        return False

    if not kwargs_are_valid(t['kwargs']):
        return False

    return True


def transaction_metadata_is_valid(m: dict):
    expected_keys = {'signature', 'timestamp'}

    if not dict_has_keys(m, expected_keys):
        return False

    if not signature_is_valid(m['signature']):
        return False

    if not number_is_valid(m['timestamp']):
        return False

    return True

def transaction_is_valid(t: dict):
    expected_keys = {'metadata', 'payload'}

    if not dict_has_keys(t, expected_keys):
        return False

    if not transaction_payload_is_valid(t['payload']):
        return False

    if not transaction_metadata_is_valid(t['metadata']):
        return False

    return True
