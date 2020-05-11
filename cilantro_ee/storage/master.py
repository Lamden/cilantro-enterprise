import cilantro_ee
from pymongo import MongoClient, DESCENDING

REPLICATION = 3
GENESIS_HASH = b'\x00' * 32
OID = '5bef52cca4259d4ca5607661'


class MasterStorage:
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
            }, MasterStorage.BLOCK)

            self.put({
                'blockNum': 0,
                'hash': b'\x00' * 32,
                'blockOwners': [b'\x00' * 32]
            }, MasterStorage.INDEX)

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
        if collection == MasterStorage.BLOCK:
            _id = self.blocks.insert_one(data)
        elif collection == MasterStorage.INDEX:
            _id = self.indexes.insert_one(data)
        elif collection == MasterStorage.TX:
            _id = self.txs.insert_one(data)
        else:
            return False

        return _id is not None

    def get_last_n(self, n, collection=INDEX):
        if collection == MasterStorage.BLOCK:
            c = self.blocks
        elif collection == MasterStorage.INDEX:
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
        self.put(block, MasterStorage.BLOCK)

        if block.get('_id') is not None:
            del block['_id']

        self.store_txs(block)

    def store_txs(self, block):
        for subblock in block['subblocks']:
            for tx in subblock['transactions']:
                self.put(tx, MasterStorage.TX)
                del tx['_id']
