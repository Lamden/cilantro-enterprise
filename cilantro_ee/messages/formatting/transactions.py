from .primatives import *


def transaction_payload_is_formatted(t: dict):
    expected_keys = {'sender', 'processor', 'nonce', 'stamps_supplied', 'contract', 'function', 'kwargs'}

    if not dict_has_keys(t, expected_keys):
        return False

    if not vk_is_formatted(t['sender']):
        return False

    if not vk_is_formatted(t['processor']):
        return False

    if not number_is_formatted(t['nonce']):
        return False

    if not number_is_formatted(t['stamps_supplied']):
        return False

    if not identifier_is_formatted(t['contract']):
        return False

    if not identifier_is_formatted(t['function']):
        return False

    if not kwargs_are_formatted(t['kwargs']):
        return False

    return True


def transaction_metadata_is_formatted(m: dict):
    expected_keys = {'signature', 'timestamp'}

    if not dict_has_keys(m, expected_keys):
        return False

    if not signature_is_formatted(m['signature']):
        return False

    if not number_is_formatted(m['timestamp']):
        return False

    return True


def transaction_is_formatted(t: dict):
    expected_keys = {'metadata', 'payload'}

    if not dict_has_keys(t, expected_keys):
        return False

    if not transaction_payload_is_formatted(t['payload']):
        return False

    if not transaction_metadata_is_formatted(t['metadata']):
        return False

    return True


def transaction_output_is_formatted(t: dict):
    expected_keys = {'hash', 'result', 'stamps_used', 'state', 'status', 'transaction'}
    if not dict_has_keys(t, expected_keys):
        return False

    if not vk_is_formatted(t['hash']):
        return False

    if not type(t['result']):
        return False

    if not number_is_formatted(t['stamps_used']):
        return False

    if not number_is_formatted(t['status']):
        return False

    if not kwargs_are_formatted(t['state']):
        return False

    if not transaction_is_formatted(t['transaction']):
        return False

    return True