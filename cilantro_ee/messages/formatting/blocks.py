from .transactions import transaction_is_formatted

sbc = {
            'input_hash': tx_batch['input_hash'],
            'transactions': results,
            'merkle_tree': merkle_tree,
            'signer': wallet.verifying_key().hex(),
            'subblock': i % parallelism,
            'previous_block_hash': previous_block_hash
        }

def subblock_contender_is_formatted(t: dict):
    pass