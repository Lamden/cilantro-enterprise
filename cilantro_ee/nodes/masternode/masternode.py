import asyncio
import hashlib
import time
from cilantro_ee import router, storage
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.storage import BlockStorage, get_latest_block_height
from cilantro_ee.nodes.masternode import contender, webserver
from cilantro_ee.formatting import primatives
import json

from cilantro_ee.nodes import base
from contracting.db.encoder import encode
from contracting.db.driver import ContractDriver

from cilantro_ee.logger.base import get_logger

mn_logger = get_logger('Masternode')

BLOCK_SERVICE = 'service'


class BlockService(router.Processor):
    def __init__(self, blocks: BlockStorage=None, driver=ContractDriver()):
        self.blocks = blocks
        self.driver = driver

    async def process_message(self, msg):
        response = None
        if primatives.dict_has_keys(msg, keys={'name', 'arg'}):
            if msg['name'] == base.GET_BLOCK:
                response = self.get_block(msg)
            elif msg['name'] == base.GET_HEIGHT:
                response = get_latest_block_height(self.driver)

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

        mn_logger.debug(f'Made new batch of {len(transactions)} transactions.')

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
        self.webserver = webserver.WebServer(
            contracting_client=self.client,
            driver=self.driver,
            blocks=self.blocks,
            wallet=self.wallet,
            port=webserver_port
        )

        self.tx_batcher = TransactionBatcher(wallet=self.wallet, queue=[])
        self.webserver.queue = self.tx_batcher.queue

        self.aggregator = contender.Aggregator(
            driver=self.driver,
        )

        self.secure_router.add_service(base.CONTENDER_SERVICE, self.aggregator.sbc_inbox)

        # Network upgrade flag
        self.active_upgrade = False

        self.masternode_contract = self.client.get_contract('masternodes')

    async def start(self, bootnodes):
        self.router.add_service(base.BLOCK_SERVICE, BlockService(self.blocks, self.driver))

        await super().start(bootnodes=bootnodes)

        # Start the block server so others can run catchup using our node as a seed.
        # Start the block contender service to participate in consensus
        self.router.add_service(base.CONTENDER_SERVICE, self.aggregator.sbc_inbox)

        # Start the webserver to accept transactions
        await self.webserver.start()

        self.log.info('Done starting...')

        # If we have no blocks in our database, we are starting a new network from scratch

        if storage.get_latest_block_height(self.driver) == 0:
            asyncio.ensure_future(self.new_blockchain_boot())
        # Otherwise, we are joining an existing network quorum
        else:
            await self.join_quorum()
        self.log.debug('returned')

    async def hang(self):
        # Wait for activity on our transaction queue or new block processor.
        # If another masternode has transactions, it will send use a new block notification.
        # If we have transactions, we will do the opposite. This 'wakes' up the network.
        mn_logger.debug('Waiting for work or blocks...')
        while len(self.tx_batcher.queue) <= 0 and len(self.new_block_processor.q) <= 0:
            if not self.running:
                return
            await asyncio.sleep(0)
        mn_logger.debug('Work / blocks available. Continuing.')

    async def broadcast_new_blockchain_started(self):
        # Check if it was us who recieved the first transaction.
        # If so, multicast a block notification to wake everyone up
        mn_logger.debug('Sending new blockchain started signal.')
        if len(self.tx_batcher.queue) > 0:
            await router.secure_multicast(
                msg=get_genesis_block(),
                service=base.NEW_BLOCK_SERVICE,
                cert_dir=self.socket_authenticator.cert_dir,
                wallet=self.wallet,
                peer_map={
                    **self.get_delegate_peers(),
                    **self.get_masternode_peers()
                },
                ctx=self.ctx
            )

    async def new_blockchain_boot(self):
        self.log.info('Fresh blockchain boot.')

        # Simply wait for the first transaction to come through
        await self.hang()
        await self.broadcast_new_blockchain_started()

        while self.running:
            await self.loop()

    async def intermediate_catchup(self):
        while self.running:

            block = await self.new_block_processor.wait_for_next_nbn()
            self.process_new_block(block)

            if self.wallet.verifying_key().hex() in self.driver.get_var(contract='masternodes',
                                                                        variable='S',
                                                                        arguments=['members']):
                break

    async def wait_for_block(self):
        self.new_block_processor.clean()

        while len(self.new_block_processor.q) <= 0:
            if not self.running:
                return
            await asyncio.sleep(0)

        block = self.new_block_processor.q.pop(0)
        self.process_new_block(block)

    async def join_quorum(self):
        # Catchup with NBNs until you have work, the join the quorum
        self.log.info('Join Quorum')

        await self.intermediate_catchup()

        await self.hang()
        await self.wait_for_block()

        while self.running:
            await self.loop()

    async def send_work(self):
        self.active_upgrade = self.driver.get_var(contract='upgrade', variable='upg_lock', mark=False)

        # Else, batch some more txs
        self.log.info(f'Sending {len(self.tx_batcher.queue)} transactions.')

        tx_batch = self.tx_batcher.pack_current_queue()

        # LOOK AT SOCKETS CLASS
        if len(self.get_delegate_peers()) == 0:
            self.log.error('No one online!')
            return

        await router.secure_multicast(
            msg=tx_batch,
            service=base.WORK_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_delegate_peers(),
            ctx=self.ctx
        )

    async def get_work_processed(self):
        await self.send_work()

        # this really should just give us a block straight up
        block = await self.aggregator.gather_subblocks(
            total_contacts=len(self.get_delegate_peers()),
            expected_subblocks=len(self.masternode_contract.quick_read("S", "members"))
        )

        encoded_block = encode(block)
        encoded_block = json.loads(encoded_block)

        self.process_new_block(encoded_block)

        self.new_block_processor.clean()

        return block

    async def confirm_new_block(self, block):
        await router.secure_multicast(
            msg=block,
            service=base.NEW_BLOCK_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map={
                **self.get_delegate_peers(),
                **self.get_masternode_peers()
            },
            ctx=self.ctx
        )

        # Clear the work here??
        self.aggregator.sbc_inbox.q.clear()

    async def loop(self):
        block = await self.get_work_processed()
        await self.hang()
        await self.confirm_new_block(block)

    def stop(self):
        super().stop()
        self.webserver.app.stop()


def get_genesis_block():
    block = {
        'hash': (b'\x00' * 32).hex(),
        'blockNum': 0,
        'previous': (b'\x00' * 32).hex(),
        'subblocks': []
    }
    return block


