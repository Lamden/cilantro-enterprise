import re
# Functions to validate Python data objects. All data must be Encoded and Decoded with the encoder in Contracting


def dict_has_keys(d: dict, keys: set):
    key_set = set(d.keys())
    return len(keys ^ key_set) == 0


def identifier_is_valid(s: str):
    try:
        iden = re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', s)
        if iden is None:
            return False
        return True
    except TypeError:
        return False


def contract_name_is_valid(s: str):
    try:
        func = re.match(r'con_^[a-zA-Z][a-zA-Z0-9_]*$', s)
        if func is None:
            return False
        return True
    except TypeError:
        return False


def vk_is_valid(s: str):
    try:
        int(s, 16)
        if len(s) != 64:
            return False
        return True
    except ValueError:
        return False


def signature_is_valid(s: str):
    try:
        int(s, 16)
        if len(s) != 128:
            return False
        return True
    except ValueError:
        return False


def number_is_valid(i: int):
    if type(i) != int:
        return False
    if i < 0:
        return False
    return True


def kwargs_are_valid(k: dict):
    for k in k.keys():
        if not identifier_is_valid(k):
            return False
    return True
