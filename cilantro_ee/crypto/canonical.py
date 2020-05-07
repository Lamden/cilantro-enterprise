import bson
import hashlib
from copy import deepcopy

from cilantro_ee.logger.base import get_logger

log = get_logger('CANON')


GENESIS_HASH = b'\x00' * 32


def format_dictionary(d: dict) -> dict:
    for k, v in d.items():
        assert type(k) == str, 'Non-string key types not allowed.'
        if type(v) == list:
            for i in range(len(v)):
                if isinstance(v[i], dict):
                    v[i] = format_dictionary(v[i])
        elif isinstance(v, dict):
            d[k] = format_dictionary(v)
    return {k: v for k, v in sorted(d.items())}


def block_from_subblocks(subblocks, previous_hash: bytes, block_num: int) -> dict:
    block_hasher = hashlib.sha3_256()
    block_hasher.update(bytes.fromhex(previous_hash))

    deserialized_subblocks = []

    for subblock in subblocks:
        if subblock is None:
            continue

        sb = format_dictionary(subblock)
        deserialized_subblocks.append(sb)

        sb_without_sigs = deepcopy(sb)
        del sb_without_sigs['signatures']

        encoded_sb = bson.BSON.encode(sb_without_sigs)
        block_hasher.update(encoded_sb)

    block = {
        'hash': block_hasher.digest().hex(),
        'blockNum': block_num,
        'previous': previous_hash,
        'subBlocks': deserialized_subblocks
    }

    return block


def verify_block(subblocks, previous_hash: bytes, proposed_hash: bytes, block_num=0):
    block = block_from_subblocks(subblocks, previous_hash, block_num)
    return block['hash'] == proposed_hash


def block_is_skip_block(block: dict):
    if len(block['subBlocks']) == 0:
        return False

    for subblock in block['subBlocks']:
        if len(subblock['transactions']):
            return False

    return True


def get_failed_block(previous_hash: bytes, block_num: int) -> dict:
    block_hasher = hashlib.sha3_256()
    block_hasher.update(bytes.fromhex(previous_hash))

    block = {
        'hash': block_hasher.digest().hex(),
        'blockNum': block_num,
        'previous': previous_hash,
        'subBlocks': []
    }
    return block


def get_genesis_block():
    block = {
        'hash': (b'\x00' * 32).hex(),
        'blockNum': 1,
        'previous': (b'\x00' * 32).hex(),
        'subBlocks': []
    }
    return block


def block_is_genesis(block):
    return block == get_genesis_block()


def block_is_failed(block, previous_hash: bytes, block_num: int):
    return block == get_failed_block(previous_hash, block_num)


def message_blob_to_dict_block(block):
    pass


def tx_hash_from_tx(tx):
    h = hashlib.sha3_256()
    tx_dict = format_dictionary(tx)
    encoded_tx = bson.BSON.encode(tx_dict)
    h.update(encoded_tx)
    return h.digest()
