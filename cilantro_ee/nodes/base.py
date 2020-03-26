from cilantro_ee.networking.network import Network
from cilantro_ee.nodes.catchup import BlockFetcher

from cilantro_ee.nodes.new_block_inbox import NBNInbox
from cilantro_ee.storage import VKBook
from cilantro_ee.contracts import sync
from cilantro_ee.networking.parameters import Parameters, ServiceType, NetworkParameters
from cilantro_ee.networking.peers import PeerServer
import cilantro_ee
import zmq.asyncio
import asyncio

from cilantro_ee.sockets.authentication import SocketAuthenticator
from cilantro_ee.storage.contract import BlockchainDriver
from contracting.client import ContractingClient

from cilantro_ee.nodes.rewards import RewardManager
from cilantro_ee.cli.utils import version_reboot

from cilantro_ee.logger.base import get_logger

from copy import deepcopy

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Node:
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict, overwrite=False,
                 bootnodes=[], network_parameters=NetworkParameters(), driver=BlockchainDriver(), mn_seed=None, debug=True):

        self.driver = driver
        self.log = get_logger('NODE')
        self.log.propagate = debug
        self.log.info(constitution)
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx
        self.ctx.max_sockets = 50_000

        self.client = ContractingClient(driver=self.driver,
                                        submission_filename=cilantro_ee.contracts.__path__[0] + '/submission.s.py')

        # Sync contracts

        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=constitution['masternodes'],
            boot_mns=constitution['masternode_min_quorum'],
            initial_delegates=constitution['delegates'],
            boot_dels=constitution['delegate_min_quorum'],
            client=self.client
        )

        self.driver.commit()
        self.driver.clear_pending_state()

        self.contacts = VKBook(
            client=self.client,
            boot_mn=constitution['masternode_min_quorum'],
            boot_del=constitution['delegate_min_quorum'],
        )

        self.current_masters = deepcopy(self.contacts.masternodes)
        self.current_delegates = deepcopy(self.contacts.delegates)

        self.parameters = Parameters(socket_base, ctx, wallet, contacts=self.contacts)

        self.socket_authenticator = SocketAuthenticator(wallet=wallet, contacts=self.contacts, ctx=self.ctx)
        self.socket_authenticator.sync_certs()

        self.elect_masternodes = self.client.get_contract('elect_masternodes')
        self.on_deck_master = self.elect_masternodes.quick_read('top_candidate')

        self.elect_delegates = self.client.get_contract('elect_delegates')
        self.on_deck_delegate = self.elect_delegates.quick_read('top_candidate')

        # Cilantro version / upgrade

        self.version_state = self.client.get_contract('upgrade')
        self.active_upgrade = self.version_state.quick_read('upg_lock')

        self.tol_mn = self.version_state.quick_read('tol_mn')
        self.tot_dl = self.version_state.quick_read('tot_dl')

        if self.tol_mn is None:
            self.tol_mn = 0

        if self.tot_dl is None:
            self.tot_dl = 0

        self.all_votes = self.tol_mn + self.tot_dl
        self.mn_votes = self.version_state.quick_read('mn_vote')
        self.dl_votes = self.version_state.quick_read('dl_vote')
        # self.pending_cnt = self.all_votes - self.vote_cnt


        # stuff

        if self.on_deck_master is not None:
            self.log.info(f'Adding on deck master {self.on_deck_master}')
            self.socket_authenticator.add_verifying_key(self.on_deck_master)

        if self.on_deck_master is not None:
            self.log.info(f'Adding on deck delegate {self.on_deck_delegate}')
            self.socket_authenticator.add_verifying_key(self.on_deck_delegate)

        self.network_parameters = network_parameters

        self.bootnodes = bootnodes
        self.constitution = constitution
        self.overwrite = overwrite

        self.block_fetcher = BlockFetcher(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.parameters,
        )

        self.network = Network(
            wallet=self.wallet,
            ctx=self.ctx,
            socket_base=socket_base,
            bootnodes=self.bootnodes,
            params=self.network_parameters,
            initial_del_quorum=deepcopy(self.contacts.delegate_quorum_min),
            initial_mn_quorum=deepcopy(self.contacts.masternode_quorum_min),
            mn_to_find=deepcopy(self.contacts.masternodes),
            del_to_find=deepcopy(self.contacts.delegates),
            mn_seed=mn_seed
        )

        self.nbn_inbox = NBNInbox(
            socket_id=self.network_parameters.resolve(
                self.socket_base,
                service_type=ServiceType.BLOCK_NOTIFICATIONS,
                bind=True),
            ctx=self.ctx,
            driver=self.driver,
            contacts=self.contacts,
            wallet=wallet
        )

        self.reward_manager = RewardManager(driver=self.driver, vkbook=self.contacts, debug=True)

        self.running = False

    async def start(self):
        await self.network.start()

        # Catchup when joining the network
        if self.network.mn_seed is not None:
            await self.block_fetcher.sync(sockets=[
                self.network_parameters.resolve(
                    self.network.mn_seed,
                    ServiceType.BLOCK_SERVER
                )
            ])

            self.log.info(self.network.peers())

            self.parameters.sockets.update(self.network.peers())

        # Start block server
        asyncio.ensure_future(self.nbn_inbox.serve())

        self.running = True

    def stop(self):
        self.network.stop()
        self.nbn_inbox.stop()
        self.running = False

    def update_sockets(self):
        # UPDATE SOCKETS IF NEEDED
        mn = self.elect_masternodes.quick_read('top_candidate')
        dl = self.elect_delegates.quick_read('top_candidate')

        self.log.info(f'Top MN is {mn}')
        self.log.info(f'Top DL is {dl}')

        update_mn = self.on_deck_master != mn and mn is not None
        update_del = self.on_deck_delegate != dl and dl is not None

        ## Check if
        nodes_changed = self.contacts.masternodes != self.current_masters \
                        or self.contacts.delegates != self.current_delegates

        if nodes_changed:
            self.current_masters = deepcopy(self.contacts.masternodes)
            self.current_delegates = deepcopy(self.contacts.delegates)

        if update_mn or update_del or nodes_changed:
            self.socket_authenticator.sync_certs()

            if update_mn:
                self.log.info(f'Adding on deck master {mn}')
                self.socket_authenticator.add_verifying_key(bytes.fromhex(mn))
                self.on_deck_master = mn

            if update_del:
                self.log.info(f'Adding on deck delegate {dl}')
                self.socket_authenticator.add_verifying_key(bytes.fromhex(dl))
                self.on_deck_master = dl

    def version_check(self):

        # check for trigger
        self.version_state = self.client.get_contract('upgrade')
        self.mn_votes = self.version_state.quick_read('mn_vote')
        self.dl_votes = self.version_state.quick_read('dl_vote')

        # self.log.info("{}".format(self.get_update_state()))

        if self.version_state:
            self.log.info('Waiting for Consensys on vote')
            self.log.info('num masters voted -> {}'.format(self.mn_votes))
            self.log.info('num delegates voted -> {}'.format(self.dl_votes))

            # check for vote consensys
            vote_consensus = self.version_state.quick_read('upg_consensus')
            if vote_consensus:
                self.log.info('Rebooting Node with new version')
                version_reboot(bn=self.bootnodes)
            else:
                self.log.info('waiting for vote on upgrade')

    def get_update_state(self):
        self.active_upgrade = self.version_state.quick_read('upg_lock')
        start_time = self.version_state.quick_read('upg_init_time')
        window = self.version_state.quick_read('upg_window')
        pepper = self.version_state.quick_read('upg_pepper')
        self.mn_votes = self.version_state.quick_read('mn_vote')
        self.dl_votes = self.version_state.quick_read('dl_vote')
        consensus = self.version_state.quick_read('upg_consensus')

        print("Upgrade -> {} Cil Pepper   -> {}\n"
              "Init time -> {}, Time Window -> {}\n"
              "Masters      -> {}\n"
              "Delegates    -> {}\n"
              "Votes        -> {}\n "
              "MN-Votes     -> {}\n "
              "DL-Votes     -> {}\n "
              "Consensus    -> {}\n"
              .format(self.active_upgrade,
                      pepper, start_time, window, self.tol_mn,
                      self.tot_dl, self.all_votes,
                      self.mn_votes, self.dl_votes,
                      consensus))

    def issue_rewards(self, block):
        # ISSUE REWARDS
        # stamps = self.reward_manager.stamps_in_block(block)
        # self.reward_manager.set_pending_rewards(stamps / self.reward_manager.stamps_per_tau)
        self.reward_manager.issue_rewards(block=block)
