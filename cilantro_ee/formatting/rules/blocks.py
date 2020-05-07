from cilantro_ee.formatting.rules.transactions import TRANSACTION_PAYLOAD_RULES
from cilantro_ee.formatting.primatives import *

MERKLE_RULES = {
    'signature': signature_is_formatted,
    'leaves': vk_is_formatted
}

SUBBLOCK_CONTENDER_RULES = {
    'input_hash': vk_is_formatted,
    'transactions': TRANSACTION_PAYLOAD_RULES,
    'merkle_tree': MERKLE_RULES,
    'signer': vk_is_formatted,
    'subblock': number_is_formatted,
    'previous': vk_is_formatted
}

SUBBLOCK_RULES = {
    'input_hash': vk_is_formatted,
    'transactions': TRANSACTION_PAYLOAD_RULES,
    'merkle_leaves': vk_is_formatted,
    'signatures': signature_is_formatted,
    'subblock': number_is_formatted,
    'previous': vk_is_formatted
}

BLOCK_RULES = {
    'hash': vk_is_formatted,
    'number': number_is_formatted,
    'previous': vk_is_formatted,
    'subblocks': SUBBLOCK_RULES
}