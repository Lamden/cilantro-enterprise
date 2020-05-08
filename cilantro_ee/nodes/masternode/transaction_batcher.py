from cilantro_ee.crypto.wallet import Wallet

import hashlib
import time

from cilantro_ee.logger.base import get_logger

log = get_logger('TXBATCHER')


class TransactionBatcher:
    def __init__(self, wallet: Wallet, queue):
        self.wallet = wallet
        self.queue = queue

    def make_batch(self, transactions):
        timestamp = int(round(time.time() * 1000))

        h = hashlib.sha3_256()
        h.update('{}'.format(timestamp).encode())
        input_hash = h.digest()

        signature = self.wallet.sign(input_hash)

        batch = {
            'transactions': transactions,
            'timestamp': timestamp,
            'signature': signature.hex(),
            'sender': self.wallet.verifying_key().hex(),
            'input_hash': input_hash.hex()
        }

        return batch

    def pack_current_queue(self, tx_number=100):
        tx_list = []

        while len(tx_list) < tx_number and len(self.queue) > 0:
            tx_list.append(self.queue.pop(0))

        batch = self.make_batch(tx_list)

        return batch
