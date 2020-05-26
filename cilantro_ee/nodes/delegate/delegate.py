from cilantro_ee.nodes.delegate import execution, work
from cilantro_ee import router, storage
from cilantro_ee.nodes import base
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

    async def accept_work(self, expected_batched):
        self.accepting_work = True
        self.process_todo_work()

        w = await work.gather_transaction_batches(
            queue=self.work,
            expected_batches=expected_batched,
            timeout=5
        )

        self.accepting_work = False

        self.log.info(f'Got {len(w)} batch(es) of work')

        return w


class Delegate(base.Node):
    def __init__(self, parallelism=4, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver)

        self.work_processor = WorkProcessor()
        self.router.add_service(WORK_SERVICE, self.work_processor)

        self.log = get_logger(f'DEL {self.wallet.vk_pretty[4:12]}')

        self.masternode_contract = self.client.get_contract('masternodes')

    async def start(self):
        self.log.debug('Starting')
        await super().start()

        asyncio.ensure_future(self.run())

        self.log.info('Running...')

    async def acquire_work(self):
        current_masternodes = self.client.get_var(contract='masternodes', variable='S', arguments=['members'])

        self.log.error(f'{len(current_masternodes)} MNS!')

        w = await self.work_processor.accept_work(expected_batched=len(current_masternodes))

        self.log.info(f'Got {len(w)} batch(es) of work')

        expected_masters = set(current_masternodes)
        work.pad_work(work=w, expected_masters=expected_masters)

        return work.filter_work(w)

    async def loop(self):
        if len(self.get_masternode_peers()) == 0:
            return

        filtered_work = await self.acquire_work()

        # Run mini catch up here to prevent 'desyncing'
        self.log.info(f'Pending Block Notifications to Process: {len(self.new_block_processor.q)}')

        while len(self.new_block_processor.q) > 0:
            block = self.new_block_processor.q.pop(0)
            self.update_state(block)

        results = execution.execute_work(
            executor=self.executor,
            driver=self.driver,
            work=filtered_work,
            wallet=self.wallet,
            previous_block_hash=storage.get_latest_block_hash(self.driver),
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])
        )

        print(results)

        await router.secure_multicast(
            msg=results,
            service=base.CONTENDER_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_masternode_peers(),
            ctx=self.ctx
        )

        self.driver.clear_pending_state()  # Add

        block = await self.new_block_processor.wait_for_next_nbn()
        self.update_state(block)

    async def run(self):
        self.log.debug('Running...')
        # if storage.get_latest_block_height(self.driver) == 0:
        #     self.log.debug('Waiting for a new block')
        #     block = await self.new_block_processor.wait_for_next_nbn()
        #     self.log.debug('Genesis block signal received.')
        #     self.process_new_block(block)


        while self.running:
            await self.loop()

    def stop(self):
        self.router.stop()
