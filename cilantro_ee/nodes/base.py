from cilantro_ee import storage, network, router, authentication, rewards, upgrade

from cilantro_ee.contracts import sync
import cilantro_ee
import zmq.asyncio
import asyncio

from contracting.client import ContractingClient

from cilantro_ee.logger.base import get_logger
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

BLOCK_SERVICE = 'service'
GET_BLOCK = 'get_block'
GET_HEIGHT = 'get_height'
NEW_BLOCK_SERVICE = 'new_blocks'


async def get_latest_block_height(ip_string: str, ctx: zmq.asyncio.Context):
    msg = {
        'name': GET_HEIGHT,
        'arg': ''
    }

    response = await router.request(
        socket_str=ip_string,
        service=BLOCK_SERVICE,
        msg=msg,
        ctx=ctx
    )

    return response


async def get_block(block_num: int, ip_string: str, ctx: zmq.asyncio.Context):
    msg = {
        'name': GET_BLOCK,
        'arg': block_num
    }

    response = await router.request(
        socket_str=ip_string,
        service=BLOCK_SERVICE,
        msg=msg,
        ctx=ctx
    )

    return response


class NewBlock(router.Processor):
    def __init__(self, driver: storage.StateDriver):
        self.q = []
        self.driver = driver
        self.log = get_logger('NBN')

    async def process_message(self, msg):
        self.q.append(msg)

    async def wait_for_next_nbn(self):
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        nbn = self.q.pop(0)

        self.q.clear()

        return nbn

    def clean(self):
        self.q = [nbn for nbn in self.q if nbn['blockNum'] >= self.driver.latest_block_num]


class Node:
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict,
                 bootnodes=[], driver=storage.StateDriver(), debug=True, store=False):

        self.driver = driver
        self.store = store

        self.blocks = None

        if self.store:
            self.blocks = storage.BlockStorage()

        self.waiting_for_confirmation = False

        self.log = get_logger('NODE')
        self.log.propagate = debug
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx

        self.client = ContractingClient(
            driver=self.driver,
            submission_filename=cilantro_ee.contracts.__path__[0] + '/submission.s.py'
        )

        self.socket_authenticator = authentication.SocketAuthenticator(ctx=self.ctx, client=self.client)
        self.socket_authenticator.refresh_governance_sockets()

        self.upgrade_manager = upgrade.UpgradeManager(client=self.client)

        self.bootnodes = bootnodes
        self.constitution = constitution

        self.router = router.Router()

        self.network = network.Network(
            wallet=wallet,
            ip_string=socket_base + '18000',
            ctx=self.ctx,
            router=self.router
        )

        self.new_block_processor = NewBlock(driver=self.driver)
        self.router.add_service(NEW_BLOCK_SERVICE, self.new_block_processor)

        self.running = False

    async def catchup(self, mn_seed):
        current = self.driver.get_latest_block_num()
        latest = await get_latest_block_height(ip_string=mn_seed, ctx=self.ctx)

        if current == 0:
            current = 1

        for i in range(current, latest):
            block = await get_block(block_num=i, ip_string=mn_seed, ctx=self.ctx)
            block = block.to_dict()
            self.process_block(block)

        while len(self.new_block_processor.q) > 0:
            block = self.new_block_processor.q.pop(0)
            self.process_block(block)

    def should_process(self, block):
        if self.waiting_for_confirmation:
            return self.driver.latest_block_num <= block['blockNum'] and block['hash'] != 'f' * 64
        else:
            return self.driver.latest_block_num < block['blockNum'] and block['hash'] != 'f' * 64

    def process_block(self, block):
        if self.should_process(block):
            self.log.info('Processing new block...')
            self.driver.update_with_block(block)

            rewards.issue_rewards(block=block, client=self.client)
            self.socket_authenticator.refresh_governance_sockets()

            if self.store:
                self.blocks.store_block(block)

        else:
            self.log.error('Could not store block...')
            if self.driver.latest_block_num >= block['blockNum']:
                self.log.error(f'Latest block num = {self.driver.latest_block_num}')
                self.log.error(f'New block num = {block["blockNum"]}')
            if block['hash'] == 'f' * 64:
                self.log.error(f'Block hash = {block["hash"]}')
            self.driver.delete_pending_nonces()

        self.driver.cache.clear()
        self.new_block_processor.clean()

        self.upgrade_manager.version_check()

    async def get_current_block_heights(self, ip_string):
        latest_block_height = await get_latest_block_height(ip_string=ip_string, ctx=self.ctx)
        local_block_height = self.driver.get_latest_block_num()
        return latest_block_height, local_block_height

    async def start(self, bootnodes):
        sync.setup_genesis_contracts(
            initial_masternodes=self.constitution['masternodes'],
            initial_delegates=self.constitution['delegates'],
            client=self.client
        )

        vks = self.constitution['masternodes'] + self.constitution['delegates']

        await self.network.start(bootnodes=bootnodes, vks=vks)

        masternode = self.constitution['masternodes'][0]
        masternode_ip = self.network.peers[masternode]

        await self.catchup(mn_seed=masternode_ip)

        self.running = True

    def stop(self):
        self.router.stop()
        self.running = False

    def _get_member_peers(self, contract_name):
        members = self.client.get_var(
            contract=contract_name,
            variable='S',
            arguments=['members']
        )

        member_peers = dict()

        for member in members:
            ip = self.network.peers.get(member)
            if ip is not None:
                member_peers[member] = ip

        return member_peers

    def get_delegate_peers(self):
        return self._get_member_peers('delegates')

    def get_masternode_peers(self):
        return self._get_member_peers('masternodes')
