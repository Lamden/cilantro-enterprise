from cilantro_ee import storage, network, router, authentication, rewards, upgrade
from cilantro_ee.crypto import canonical
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.contracts import sync
from contracting.db.driver import ContractDriver, encode
import cilantro_ee
import zmq.asyncio
import asyncio
import json
from contracting.client import ContractingClient
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from cilantro_ee.logger.base import get_logger


BLOCK_SERVICE = 'catchup'
NEW_BLOCK_SERVICE = 'new_blocks'
WORK_SERVICE = 'work'
CONTENDER_SERVICE = 'contenders'

GET_BLOCK = 'get_block'
GET_HEIGHT = 'get_height'

log = get_logger('Base')


async def get_latest_block_height(wallet: Wallet, vk: str, ip: str, ctx: zmq.asyncio.Context):
    msg = {
        'name': GET_HEIGHT,
        'arg': ''
    }

    log.debug('Sending latest block height msg...')

    response = await router.secure_request(
        ip=ip,
        vk=vk,
        wallet=wallet,
        service=BLOCK_SERVICE,
        msg=msg,
        ctx=ctx,
    )

    return response


async def get_block(block_num: int, wallet: Wallet, vk: str, ip: str, ctx: zmq.asyncio.Context):
    msg = {
        'name': GET_BLOCK,
        'arg': block_num
    }

    response = await router.secure_request(
        ip=ip,
        vk=vk,
        wallet=wallet,
        service=BLOCK_SERVICE,
        msg=msg,
        ctx=ctx,
    )

    return response


class NewBlock(router.Processor):
    def __init__(self, driver: ContractDriver):
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

    def clean(self, height):
        self.q = [nbn for nbn in self.q if nbn['number'] > height]


def ensure_in_constitution(verifying_key: str, constitution: dict):
    masternodes = constitution['masternodes']
    delegates = constitution['delegates']

    is_masternode = verifying_key in masternodes.values()
    is_delegate = verifying_key in delegates.values()

    assert is_masternode or is_delegate, 'You are not in the constitution!'

class Node:
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict, bootnodes={}, blocks=None,
                 driver=ContractDriver(), debug=True, store=False, seed=None,
                 genesis_path=cilantro_ee.contracts.__path__[0], reward_manager=rewards.RewardManager(), nonces=storage.NonceStorage()):

        self.driver = driver
        self.nonces = nonces
        self.store = store

        self.seed = seed

        self.blocks = blocks

        if self.store:
            self.blocks = storage.BlockStorage()

        self.log = get_logger('NODE')
        self.log.propagate = debug
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx

        self.genesis_path = genesis_path

        self.client = ContractingClient(
            driver=self.driver,
            submission_filename=genesis_path + '/submission.s.py'
        )

        self.bootnodes = bootnodes
        self.constitution = constitution

        self.seed_genesis_contracts()

        self.socket_authenticator = authentication.SocketAuthenticator(
            bootnodes=self.bootnodes, ctx=self.ctx, client=self.client
        )

        self.upgrade_manager = upgrade.UpgradeManager(client=self.client, pepper='cilantro')

        self.router = router.Router(
            socket_id=socket_base,
            ctx=self.ctx,
            wallet=wallet,
            secure=True
        )

        self.network = network.Network(
            wallet=wallet,
            ip_string=socket_base,
            ctx=self.ctx,
            router=self.router
        )

        self.new_block_processor = NewBlock(driver=self.driver)
        self.router.add_service(NEW_BLOCK_SERVICE, self.new_block_processor)

        self.running = False
        self.upgrade = False

        self.reward_manager = reward_manager

        self.current_height = storage.get_latest_block_height(self.driver)
        self.current_hash = storage.get_latest_block_hash(self.driver)

    def seed_genesis_contracts(self):
        sync.setup_genesis_contracts(
            initial_masternodes=self.constitution['masternodes'],
            initial_delegates=self.constitution['delegates'],
            client=self.client,
            filename=self.genesis_path + '/genesis.json',
            root=self.genesis_path
        )

    async def catchup(self, mn_seed, mn_vk):
        # Get the current latest block stored and the latest block of the network
        current = self.current_height
        latest = await get_latest_block_height(
            ip=mn_seed,
            vk=mn_vk,
            wallet=self.wallet,
            ctx=self.ctx
        )

        # assert type(latest) != dict, 'Provided node is not in sync.'

        self.log.info(f'Current: {current}, Latest: {latest}')

        if latest == 0 or latest is None or type(latest) == dict:
            return

        # Increment current by one. Don't count the genesis block.
        if current == 0:
            current = 1

        # Find the missing blocks process them
        for i in range(current, latest + 1):
            block = await get_block(
                block_num=i,
                ip=mn_seed,
                vk=mn_vk,
                wallet=self.wallet,
                ctx=self.ctx
            )
            self.process_new_block(block)

        # Process any blocks that were made while we were catching up
        while len(self.new_block_processor.q) > 0:
            block = self.new_block_processor.q.pop(0)
            self.process_new_block(block)

    def should_process(self, block):
        log.debug(f'got block #{block["number"]}')
        # Test if block failed immediately
        if block['hash'] == 'f' * 64:
            return False

        # Get current metastate

        # Test if block contains the same metastate
        if block['number'] != self.current_height + 1:
            log.debug('Lower number block...')
            return False

        if block['previous'] != self.current_hash:
            log.debug('Past hash mismatch')
            return False

        # If so, use metastate and subblocks to create the 'expected' block
        expected_block = canonical.block_from_subblocks(
            subblocks=block['subblocks'],
            previous_hash=self.current_hash,
            block_num=self.current_height + 1
        )

        # Return if the block contains the expected information
        good = block == expected_block
        if good:
            log.debug('Block is good')
        else:
            log.debug('Block is not expected')

        return good

    def update_state(self, block):
        self.driver.clear_pending_state()

        # Check if the block is valid
        if self.should_process(block):
            log.debug('Updating with new block')
            # Commit the state changes and nonces to the database
            storage.update_state_with_block(
                block=block,
                driver=self.driver,
                nonces=self.nonces
            )

            # Calculate and issue the rewards for the governance nodes
            self.reward_manager.issue_rewards(
                block=block,
                client=self.client
            )

        self.current_height = storage.get_latest_block_height(self.driver)
        self.current_hash = storage.get_latest_block_hash(self.driver)

        self.driver.commit()
        self.driver.clear_pending_state()

    def process_new_block(self, block):
        # Update the state and refresh the sockets so new nodes can join
        self.update_state(block)
        self.socket_authenticator.refresh_governance_sockets()

        # Store the block if it's a masternode
        if self.store:
            encoded_block = encode(block)
            encoded_block = json.loads(encoded_block)

            self.blocks.store_block(encoded_block)

        # Prepare for the next block by flushing out driver and notification state
        # self.new_block_processor.clean()

        # Finally, check and initiate an upgrade if one needs to be done
        self.upgrade_manager = upgrade.UpgradeManager(client=self.client, pepper='cilantro')
        self.upgrade_manager.version_check()

        self.new_block_processor.clean(self.current_height)

    async def start(self):
        asyncio.ensure_future(self.router.serve())

        # Get the set of VKs we are looking for from the constitution argument
        vks = self.constitution['masternodes'] + self.constitution['delegates']

        for node in self.bootnodes.keys():
            self.socket_authenticator.add_verifying_key(node)

        self.socket_authenticator.configure()

        # Use it to boot up the network
        await self.network.start(bootnodes=self.bootnodes, vks=vks)

        masternode_ip = None
        masternode = None

        if self.seed is not None:
            for k, v in self.bootnodes.items():
                self.log.info(k, v)
                if v == self.seed:
                    masternode = k
                    masternode_ip = v
        else:
            masternode = self.constitution['masternodes'][0]
            masternode_ip = self.network.peers[masternode]

        self.log.debug(f'Catching up from MN: {masternode}')

        # Use this IP to request any missed blocks
        await self.catchup(mn_seed=masternode_ip, mn_vk=masternode)

        # Refresh the sockets to accept new nodes
        self.socket_authenticator.refresh_governance_sockets()

        # Start running
        self.running = True

    def stop(self):
        # Kill the router and throw the running flag to stop the loop
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
