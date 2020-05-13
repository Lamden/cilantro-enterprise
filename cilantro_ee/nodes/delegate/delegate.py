from cilantro_ee.nodes.delegate import execution
from cilantro_ee.nodes.delegate.work import gather_transaction_batches, pad_work, filter_work
from cilantro_ee import router
from cilantro_ee.nodes.base import Node
from cilantro_ee.logger.base import get_logger
import asyncio

from contracting.execution.executor import Executor
from contracting.db.encoder import encode

WORK_SERVICE = 'work'


class WorkProcessor(router.Processor):
    def __init__(self, debug=True):
        self.work = {}

        self.todo = []
        self.accepting_work = False

        self.log = get_logger('DEL WI')
        self.log.propagate = debug

    async def process_message(self, msg):
        if not self.accepting_work:
            self.log.info('TODO')
            self.todo.append(msg)

        else:
            self.verify_work(msg)

    def verify_work(self, msg):
        self.work[msg['sender']] = msg

    def process_todo_work(self):
        self.log.info(f'Current todo {self.todo}')

        for work in self.todo:
            self.verify_work(work)

        self.todo.clear()


class Delegate(Node):
    def __init__(self, parallelism=4, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver)

        self.work_processor = WorkProcessor()
        self.router.add_service(WORK_SERVICE, self.work_processor)

        self.pending_sbcs = set()

        self.log = get_logger(f'DEL {self.wallet.vk_pretty[4:12]}')

        self.masternode_contract = self.client.get_contract('masternodes')

    async def start(self):
        await super().start()

        asyncio.ensure_future(self.run())

        self.log.info('Running...')

    async def acquire_work(self):
        if len(self.parameters.sockets) == 0:
            return

        self.log.error(f'{len(self.masternode_contract.quick_read("S", "members"))} MNS!')

        self.work_processor.accepting_work = True
        self.work_processor.process_todo_work()

        work = await gather_transaction_batches(
            queue=self.work_processor.work,
            expected_batches=len(self.masternode_contract.quick_read("S", "members")),
            timeout=5
        )

        self.work_processor.accepting_work = False

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

        return results

    async def run(self):
        # If first block, just wait for masters to send the genesis NBN
        if self.driver.latest_block_num == 0:
            nbn = await self.new_block_processor.wait_for_next_nbn()
            self.process_block(nbn)
            self.version_check()

        while self.running:
            filtered_work = await self.acquire_work()

            # Run mini catch up here to prevent 'desyncing'
            self.log.info(f'Pending Block Notifications to Process: {len(self.new_block_processor.q)}')

            while len(self.new_block_processor.q) > 0:
                block = self.new_block_processor.q.pop(0)
                self.process_block(block)

            results = execution.execute_work(
                executor=self.executor,
                driver=self.driver,
                work=filtered_work,
                wallet=self.wallet,
                previous_block_hash=self.driver.latest_block_hash,
                stamp_cost=self.reward_manager.stamps_per_tau
            )

            print(results)

            await self.masternode_socket_book.send_to_peers(
                msg=encode(results).encode()
            )

            self.driver.clear_pending_state() # Add

            self.waiting_for_confirmation = True

            nbn = await self.new_block_processor.wait_for_next_nbn()
            self.process_block(nbn)

            self.waiting_for_confirmation = False

    def stop(self):
        self.router.stop()
