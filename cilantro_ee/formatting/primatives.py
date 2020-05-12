import re


# Recursive engine to process rules on validation. Define base rules here and reference other rule sets to make
# object like things.
def recurse_rules(d: dict, rule: dict):
    if callable(rule):
        return rule(d)

    for key, subrule in rule.items():
        arg = d[key]

        if type(arg) == dict:
            if not recurse_rules(arg, subrule):
                return False

        if type(arg) == list:
            for a in arg:
                if not recurse_rules(a, subrule):
                    return False

        if callable(subrule):
            if not subrule(arg):
                return False

    return True


def check_format(d: dict, rule: dict):
    expected_keys = set(rule.keys())

    if not dict_has_keys(d, expected_keys):
        return False

    return recurse_rules(d, rule)


def dict_has_keys(d: dict, keys: set):
    key_set = set(d.keys())
    return len(keys ^ key_set) == 0


def identifier_is_formatted(s: str):
    try:
        iden = re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', s)
        if iden is None:
            return False
        return True
    except TypeError:
        return False


def contract_name_is_formatted(s: str):
    try:
        func = re.match(r'^con_[a-zA-Z][a-zA-Z0-9_]*$', s)
        if func is None:
            return False
        return True
    except TypeError:
        return False


def vk_is_formatted(s: str):
    try:
        int(s, 16)
        if len(s) != 64:
            return False
        return True
    except ValueError:
        return False
    except TypeError:
        return False


def signature_is_formatted(s: str):
    try:
        int(s, 16)
        if len(s) != 128:
            return False
        return True
    except ValueError:
        return False
    except TypeError:
        return False


def number_is_formatted(i: int):
    if type(i) != int:
        return False
    if i < 0:
        return False
    return True


def kwargs_are_formatted(k: dict):
    for k in k.keys():
        if not identifier_is_formatted(k):
            return False
    return True


def is_string(s: str):
    return type(s) == str


def is_dict(d: dict):
    return type(d) == dict


def is_tcp_or_ipc_string(s):
    return True
