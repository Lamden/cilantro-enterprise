from cilantro_ee.nodes.work_inbox import WorkInbox
from cilantro_ee.networking.parameters import ServiceType

from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType

from cilantro_ee.nodes.delegate import execution
from cilantro_ee.nodes.delegate.work import gather_transaction_batches, pad_work, filter_work
from cilantro_ee.sockets.outbox import Peers, MN

from cilantro_ee.nodes.base import Node
from cilantro_ee.logger.base import get_logger
import asyncio

from contracting.execution.executor import Executor


class Delegate(Node):
    def __init__(self, parallelism=4, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver)

        self.work_inbox = WorkInbox(
            socket_id=self.network_parameters.resolve(self.socket_base, ServiceType.INCOMING_WORK, bind=True),
            driver=self.driver,
            ctx=self.ctx,
            client=self.client,
            wallet=self.wallet
        )

        self.pending_sbcs = set()

        self.log = get_logger(f'DEL {self.wallet.vk_pretty[4:12]}')

        self.masternode_socket_book = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.parameters,
            service_type=ServiceType.BLOCK_AGGREGATOR,
            node_type=MN
        )

        self.masternode_contract = self.client.get_contract('masternodes')

    async def start(self):
        await super().start()

        asyncio.ensure_future(self.work_inbox.serve())
        asyncio.ensure_future(self.run())

        self.log.info('Running...')

    def masternode_aggregator_sockets(self):
        return list(self.parameters.get_masternode_sockets(service=ServiceType.BLOCK_AGGREGATOR).values())

    async def acquire_work(self):
        await self.parameters.refresh()
        self.masternode_socket_book.sync_sockets()

        if len(self.parameters.sockets) == 0:
            return

        self.log.error(f'{len(self.masternode_contract.quick_read("S", "members"))} MNS!')

        self.work_inbox.accepting_work = True
        self.work_inbox.process_todo_work()

        work = await gather_transaction_batches(
            queue=self.work_inbox.work,
            expected_batches=len(self.masternode_contract.quick_read("S", "members")),
            timeout=5
        )

        self.work_inbox.accepting_work = False

        self.log.info(f'Got {len(work)} batch(es) of work')

        expected_masters = set(self.masternode_contract.quick_read("S", "members"))
        pad_work(work=work, expected_masters=expected_masters)

        return filter_work(work)

    def process_work(self, filtered_work):
        results = execution.execute_work(
            executor=self.executor,
            driver=self.driver,
            work=filtered_work,
            wallet=self.wallet,
            previous_block_hash=self.driver.latest_block_hash,
            stamp_cost=self.reward_manager.stamps_per_tau
        )

        self.log.info(results)

        # Send out the contenders to masternodes
        return Message.get_message_packed_2(
            msg_type=MessageType.SUBBLOCK_CONTENDERS,
            contenders=[sb for sb in results]
        )

    async def run(self):
        # If first block, just wait for masters to send the genesis NBN
        if self.driver.latest_block_num == 0:
            nbn = await self.nbn_inbox.wait_for_next_nbn()
            self.process_block(nbn)
            self.version_check()

        while self.running:
            await self.parameters.refresh()
            self.masternode_socket_book.sync_sockets()

            filtered_work = await self.acquire_work()

            # Run mini catch up here to prevent 'desyncing'
            self.log.info(f'Pending Block Notifications to Process: {len(self.nbn_inbox.q)}')

            while len(self.nbn_inbox.q) > 0:
                block = self.nbn_inbox.q.pop(0)
                self.process_block(block)

            self.log.info(filtered_work)

            sbc_msg = self.process_work(filtered_work)

            await self.masternode_socket_book.send_to_peers(
                msg=sbc_msg
            )

            self.driver.clear_pending_state() # Add

            self.waiting_for_confirmation = True

            nbn = await self.nbn_inbox.wait_for_next_nbn()
            self.process_nbn(nbn)
            self.version_check()

            self.waiting_for_confirmation = False

    def stop(self):
        self.running = False
        self.network.stop()
        self.work_inbox.stop()
        self.nbn_inbox.stop()
