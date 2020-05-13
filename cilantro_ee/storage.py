from contracting.db.driver import ContractDriver
from pymongo import MongoClient, DESCENDING

import cilantro_ee
from cilantro_ee.logger.base import get_logger

BLOCK_HASH_KEY = '_current_block_hash'
BLOCK_NUM_KEY = '_current_block_num'
NONCE_KEY = '__n'
PENDING_NONCE_KEY = '__pn'

log = get_logger('STATE')


class StateDriver(ContractDriver):
    def get_latest_block_hash(self):
        block_hash = self.driver.get(BLOCK_HASH_KEY)
        if block_hash is None:
            return '0' * 64
        return block_hash

    def set_latest_block_hash(self, v: str):
        if type(v) == bytes:
            v = v.hex()
        assert len(v) == 64, 'Hash provided is not 32 bytes.'
        self.driver.set(BLOCK_HASH_KEY, v)

    latest_block_hash = property(get_latest_block_hash, set_latest_block_hash)

    def get_latest_block_num(self) -> int:
        num = self.driver.get(BLOCK_NUM_KEY)

        if num is None:
            return 0

        num = int(num)

        return num

    def set_latest_block_num(self, v):
        v = int(v)
        assert v >= 0, 'Block number must be positive integer.'

        # v = str(v).encode()

        self.driver.set(BLOCK_NUM_KEY, v)

    latest_block_num = property(get_latest_block_num, set_latest_block_num)

    def set_transaction_data(self, tx):
        if tx['state'] is not None and len(tx['state']) > 0:
            for delta in tx['state']:
                self.driver.set(delta['key'], delta['value']) # driver.driver bypasses cache
                log.info(f"{delta['key']} -> {delta['value']}")

    def update_with_block(self, block):
        if self.latest_block_hash != block['previous']:
            log.error('BLOCK MISMATCH!!!')

        self.latest_block_num += 1

        for sb in block['subblocks']:
            for tx in sb['transactions']:
                self.set_transaction_data(tx=tx)

        # Commit new nonces
        self.commit_nonces()
        self.delete_pending_nonces()

        # Update our block hash and block num
        self.set_latest_block_hash(block['hash'])

    @staticmethod
    def n_key(key, processor, sender):
        if type(processor) == bytes:
            processor = processor.hex()

        if type(sender) == bytes:
            sender = sender.hex()

        return ':'.join([key, processor, sender])

    # Nonce methods
    def get_pending_nonce(self, processor: bytes, sender: bytes):
        return self.driver.get(self.n_key(PENDING_NONCE_KEY, processor, sender))

    def get_nonce(self, processor: bytes, sender: bytes):
        return self.driver.get(self.n_key(NONCE_KEY, processor, sender))

    def set_pending_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.driver.set(self.n_key(PENDING_NONCE_KEY, processor, sender), nonce)

    def set_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.driver.set(self.n_key(NONCE_KEY, processor, sender), nonce)

    def delete_pending_nonce(self, processor: bytes, sender: bytes):
        self.driver.delete(self.n_key(PENDING_NONCE_KEY, processor, sender))

    def get_latest_nonce(self, processor:bytes, sender: bytes):
        nonce = self.get_pending_nonce(processor, sender)

        if nonce is None:
            nonce = self.get_nonce(processor, sender)

        if nonce is None:
            nonce = 0

        return nonce

    def commit_nonces(self):
        for n in self.driver.iter(PENDING_NONCE_KEY):
            _, processor, sender = n.split(':')

            processor = bytes.fromhex(processor)
            sender = bytes.fromhex(sender)

            nonce = self.get_pending_nonce(processor=processor, sender=sender)

            self.set_nonce(processor=processor, sender=sender, nonce=nonce)
            self.delete(n, mark=False)

    def delete_pending_nonces(self):
        for nonce in self.keys(PENDING_NONCE_KEY):
            self.delete(nonce, mark=False)

    def iter(self, *args, **kwargs):
        return self.driver.iter(*args, **kwargs)


class BlockStorage:
    BLOCK = 0
    INDEX = 1
    TX = 2

    def __init__(self, port=27027, config_path=cilantro_ee.__path__[0]):
        # Setup configuration file to read constants
        self.config_path = config_path

        self.port = port

        self.client = MongoClient()
        self.db = self.client.get_database('blockchain')

        self.blocks = self.db['blocks']
        self.indexes = self.db['index']
        self.txs = self.db['tx']

        if self.get_block(0) is None:
            self.put({
                'blockNum': 0,
                'hash': b'\x00' * 32,
                'blockOwners': [b'\x00' * 32]
            }, BlockStorage.BLOCK)

            self.put({
                'blockNum': 0,
                'hash': b'\x00' * 32,
                'blockOwners': [b'\x00' * 32]
            }, BlockStorage.INDEX)

    def q(self, v):
        if isinstance(v, int):
            return {'blockNum': v}
        return {'hash': v}

    def get_block(self, v=None):
        if v is None:
            return None

        q = self.q(v)
        block = self.blocks.find_one(q)

        if block is not None:
            block.pop('_id')

        return block

    def put(self, data, collection=BLOCK):
        if collection == BlockStorage.BLOCK:
            _id = self.blocks.insert_one(data)
        elif collection == BlockStorage.INDEX:
            _id = self.indexes.insert_one(data)
        elif collection == BlockStorage.TX:
            _id = self.txs.insert_one(data)
        else:
            return False

        return _id is not None

    def get_last_n(self, n, collection=INDEX):
        if collection == BlockStorage.BLOCK:
            c = self.blocks
        elif collection == BlockStorage.INDEX:
            c = self.indexes
        else:
            return None

        block_query = c.find({}, {'_id': False}).sort(
            'blockNum', DESCENDING
        ).limit(n)

        blocks = [block for block in block_query]

        if len(blocks) > 1:
            first_block_num = blocks[0].get('blockNum')
            last_block_num = blocks[-1].get('blockNum')

            assert first_block_num > last_block_num, "Blocks are not descending."

        return blocks

    def get_owners(self, v):
        q = self.q(v)
        index = self.indexes.find_one(q)

        if index is None:
            return index

        owners = index.get('blockOwners')

        return owners

    def get_index(self, v):
        q = self.q(v)
        block = self.indexes.find_one(q)

        if block is not None:
            block.pop('_id')

        return block

    def get_tx(self, h):
        tx = self.txs.find_one({'hash': h})

        if tx is not None:
            tx.pop('_id')

        return tx

    def drop_collections(self):
        self.blocks.remove()
        self.indexes.remove()

    def store_block(self, block):
        self.put(block, BlockStorage.BLOCK)

        if block.get('_id') is not None:
            del block['_id']

        self.store_txs(block)

    def store_txs(self, block):
        for subblock in block['subblocks']:
            for tx in subblock['transactions']:
                self.put(tx, BlockStorage.TX)
                del tx['_id']
