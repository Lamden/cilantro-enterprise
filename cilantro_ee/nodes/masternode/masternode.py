import asyncio
import hashlib
import time

from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.nodes.masternode.server.routes import WebServer
from cilantro_ee.nodes.masternode.contender.contender import Aggregator
from cilantro_ee.storage import StateDriver, BlockStorage
from cilantro_ee.router import Processor
from cilantro_ee.formatting import primatives
import json

from cilantro_ee.nodes import base
from contracting.db.encoder import encode


BLOCK_SERVICE = 'service'


class BlockService(Processor):
    def __init__(self, blocks: BlockStorage=None, driver=StateDriver()):
        self.blocks = blocks
        self.driver = driver

    async def process_message(self, msg):
        response = None
        if primatives.dict_has_keys(msg, keys={'name', 'arg'}):
            if msg['name'] == base.GET_BLOCK:
                response = self.get_block(msg)
            elif msg['name'] == base.GET_HEIGHT:
                response = self.driver.get_latest_block_num()

        return response

    def get_block(self, command):
        num = command.get('arg')
        if not primatives.number_is_formatted(num):
            return None

        block = self.blocks.get_block(num)

        if block is None:
            return None

        return block


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


class Masternode(base.Node):
    def __init__(self, webserver_port=8080, *args, **kwargs):
        super().__init__(store=True, *args, **kwargs)
        # Services
        self.webserver = WebServer(
            contracting_client=self.client,
            driver=self.driver,
            blocks=self.blocks,
            wallet=self.wallet,
            port=webserver_port
        )

        self.tx_batcher = TransactionBatcher(wallet=self.wallet, queue=[])
        self.current_nbn = get_genesis_block()

        self.aggregator = Aggregator(
            socket_id=self.network_parameters.resolve(
                self.socket_base,
                service_type=ServiceType.BLOCK_AGGREGATOR,
                bind=True),
            ctx=self.ctx,
            driver=self.driver,
            wallet=self.wallet
        )

        # Network upgrade flag
        self.active_upgrade = False

        self.masternode_contract = self.client.get_contract('masternodes')

    async def start(self, bootnodes):
        await super().start(bootnodes=bootnodes)

        latest_block = self.blocks.get_last_n(1, self.blocks.BLOCK)[0]
        self.log.info(latest_block)
        self.driver.latest_block_num = latest_block['blockNum']
        self.driver.latest_block_hash = latest_block['hash']

        self.router.add_service(BLOCK_SERVICE, BlockService(self.blocks, self.driver))

        self.webserver.queue = self.tx_batcher.queue
        await self.webserver.start()

        self.log.info('Done starting...')

        asyncio.ensure_future(self.aggregator.start())
        asyncio.ensure_future(self.run())

    async def run(self):
        self.log.info('Running...')
        if self.driver.latest_block_num == 0: # or len(self.contacts.masternodes) == 1:
            await self.new_blockchain_boot()
        else:
            await self.join_quorum()

    async def new_blockchain_boot(self):
        self.log.info('Fresh blockchain boot.')

        while len(self.tx_batcher.queue) == 0 and len(self.new_block_processor.q) == 0:
            if not self.running:
                return
            await asyncio.sleep(0)

        if len(self.tx_batcher.queue) > 0:
            msg = get_genesis_block()

            ## SEND OUT VIA SOCKETS CLASS
            sends = await self.nbn_socket_book.send_to_peers(
                msg=encode(msg).encode()
            )

            self.log.info(f'{sends}')

            # await multicast(self.ctx, msg, self.nbn_sockets())

        if len(self.contacts.masternodes) > 1:
            self.driver.set_latest_block_num(1)

        await self.process_blocks()

    async def join_quorum(self):
        # Catchup with NBNs until you have work, the join the quorum
        self.log.info('Join Quorum')

        block = await self.new_block_processor.wait_for_next_nbn()

        while self.wallet.verifying_key().hex() not in self.masternode_contract.quick_read("S", "members"):
            # if block number does not equal one more than the current block number
            # ask for the blocks before it
            if block['blockNum'] > self.driver.latest_block_num + 1:
                last_block = await self.block_fetcher.get_block_from_master(block['blockNum']-1, self.network_parameters.resolve(
                    self.network.mn_seed,
                    ServiceType.BLOCK_SERVER
                ))

                self.process_block(last_block.to_dict())

            self.process_block(block)

            block = await self.new_block_processor.wait_for_next_nbn()

        await self.wait_for_work(block)

        await self.process_blocks()

    async def send_work(self):

        driver = StateDriver()
        self.active_upgrade = driver.get_var(contract='upgrade', variable='upg_lock', mark=False)

        # Else, batch some more txs
        self.log.info(f'Sending {len(self.tx_batcher.queue)} transactions.')

        tx_batch = self.tx_batcher.pack_current_queue()

        # LOOK AT SOCKETS CLASS
        if len(self.dl_wk_sks()) == 0:
            self.log.error('No one online!')
            return

        return await self.delegate_work_socket_book.send_to_peers(
               msg=encode(tx_batch).encode()
           )

    async def wait_for_work(self, block):
        is_skip_block = block_is_skip_block(block)

        if is_skip_block:
            self.log.info('SKIP. Going to hang now...')

        # If so, hang until you get a new block or some work OR NBN
        self.new_block_processor.clean()

        while len(self.tx_batcher.queue) <= 0:
            if len(self.new_block_processor.q) > 0:
                self.log.info('''
=== Got a New Block Notification from another Master ===
                ''')
                break

            await asyncio.sleep(0)

    async def process_blocks(self):
        while self.running:
            sends = await self.send_work()

            if sends is None:
                return

            # this really should just give us a block straight up
            block = await self.aggregator.gather_subblocks(
                total_contacts=len(self.contacts.delegates),
                expected_subblocks=len(self.masternode_contract.quick_read("S", "members"))
            )

            encoded_block = encode(block)
            encoded_block = json.loads(encoded_block)
            print(encoded_block)

            self.process_block(encoded_block)

            await self.wait_for_work(encoded_block)

            sends = await self.new_block_processor.send_to_peers(
                msg=encode(block).encode()
            )

            self.log.info(f'NBN SENDS {sends}')

            # Clear the work here??
            self.aggregator.sbc_inbox.q.clear()

    def stop(self):
        super().stop()
        self.webserver.app.stop()


def block_is_skip_block(block: dict):
    if len(block['subblocks']) == 0:
        return False

    for subblock in block['subblocks']:
        if len(subblock['transactions']):
            return False

    return True


def get_genesis_block():
    block = {
        'hash': (b'\x00' * 32).hex(),
        'blockNum': 1,
        'previous': (b'\x00' * 32).hex(),
        'subblocks': []
    }
    return block


