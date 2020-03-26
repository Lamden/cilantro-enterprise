import asyncio
from cilantro_ee.nodes.catchup import BlockServer
from cilantro_ee.sockets.outbox import Peers, MN, DEL, ALL
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.storage import CilantroStorageDriver
from cilantro_ee.sockets.services import secure_multicast
from cilantro_ee.nodes.masternode.webserver import WebServer
from cilantro_ee.nodes.masternode.block_contender import Aggregator
from cilantro_ee.networking.parameters import ServiceType
from cilantro_ee.crypto import canonical
from cilantro_ee.storage.contract import BlockchainDriver


from cilantro_ee.nodes.base import Node


class Masternode(Node):
    def __init__(self, webserver_port=8080, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.blocks = CilantroStorageDriver(key=self.wallet.verifying_key())

        # Services
        self.block_server = BlockServer(
            wallet=self.wallet,
            socket_base=self.socket_base,
            network_parameters=self.network_parameters,
            blocks=self.blocks
        )

        self.webserver = WebServer(
            contracting_client=self.client,
            driver=self.driver,
            blocks=self.blocks,
            wallet=self.wallet,
            port=webserver_port
        )

        self.tx_batcher = TransactionBatcher(wallet=self.wallet, queue=[])
        self.current_nbn = canonical.get_genesis_block()

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

        self.nbn_socket_book = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.parameters,
            service_type=ServiceType.BLOCK_NOTIFICATIONS,
            node_type=ALL
        )

        self.delegate_work_socket_book = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.parameters,
            service_type=ServiceType.INCOMING_WORK,
            node_type=DEL
        )

    async def start(self):
        await super().start()
        # Start block server to provide catchup to other nodes

        latest_block = self.blocks.get_last_n(1, self.blocks.BLOCK)[0]
        self.log.info(latest_block)
        self.driver.latest_block_num = latest_block['blockNum']
        self.driver.latest_block_hash = latest_block['hash']

        #
        asyncio.ensure_future(self.block_server.serve())
        self.webserver.queue = self.tx_batcher.queue
        await self.webserver.start()
        self.log.info('Done starting...')
        asyncio.ensure_future(self.aggregator.start())
        asyncio.ensure_future(self.run())

    ## DELETE
    def delegate_work_sockets(self):
        return list(self.parameters.get_delegate_sockets(service=ServiceType.INCOMING_WORK).values())

    ## DELETE
    def nbn_sockets(self):
        return list(self.parameters.get_all_sockets(service=ServiceType.BLOCK_NOTIFICATIONS).values())


    def dl_wk_sks(self):
        return list(self.parameters.get_delegate_sockets(service=ServiceType.INCOMING_WORK).items())

    def nbn_sks(self):
        return list(self.parameters.get_all_sockets(service=ServiceType.BLOCK_NOTIFICATIONS).items())

    async def run(self):
        self.log.info('Running...')
        if self.driver.latest_block_num == 0 or len(self.contacts.masternodes) == 1:
            await self.new_blockchain_boot()
        else:
            await self.join_quorum()

    async def new_blockchain_boot(self):
        self.log.info('Fresh blockchain boot.')

        await self.parameters.refresh()
        self.nbn_socket_book.sync_sockets()
        self.delegate_work_socket_book.sync_sockets()

        while len(self.tx_batcher.queue) == 0 and len(self.nbn_inbox.q) == 0:
            if not self.running:
                return
            await asyncio.sleep(0)

        if len(self.tx_batcher.queue) > 0:
            msg = canonical.dict_to_msg_block(canonical.get_genesis_block())

            ## SEND OUT VIA SOCKETS CLASS
            sends = await self.nbn_socket_book.send_to_peers(
                msg=msg
            )

            self.log.info(f'{sends}')

            # await multicast(self.ctx, msg, self.nbn_sockets())

        if len(self.contacts.masternodes) > 1:
            self.driver.set_latest_block_num(1)

        await self.process_blocks()

    async def join_quorum(self):
        # Catchup with NBNs until you have work, the join the quorum
        self.log.info('Join Quorum')
        nbn = await self.nbn_inbox.wait_for_next_nbn()

        # Update with state
        self.driver.update_with_block(nbn)
        self.driver.commit()
        self.blocks.put(nbn, self.blocks.BLOCK)

        while len(self.tx_batcher.queue) == 0:
            await asyncio.sleep(0)
            if len(self.nbn_inbox.q) > 0:
                nbn = self.nbn_inbox.q.pop(0)
                self.driver.update_with_block(nbn)
                self.blocks.put(nbn, self.blocks.BLOCK)

        await self.process_blocks()

    async def send_work(self):

        driver = BlockchainDriver()
        self.active_upgrade = driver.get_var(contract='upgrade', variable='upg_lock', mark=False)

        # Else, batch some more txs
        self.log.info(f'Sending {len(self.tx_batcher.queue)} transactions.')

        if self.active_upgrade is False:
            tx_batch = self.tx_batcher.pack_current_queue()
        elif self.active_upgrade is True:
            consensus_reached = driver.get_var(contract='upgrade', variable='upg_consensus', mark=False)
            if consensus_reached is True:
                tx_batch = self.tx_batcher.make_empty_batch()
                self.log.info('Triggering version reboot')
                # we should never be here node reset should have been done when state changed
            else:
                tx_batch = self.tx_batcher.pack_current_queue()
        else:
            tx_batch = self.tx_batcher.pack_current_queue()

        # LOOK AT SOCKETS CLASS
        if len(self.dl_wk_sks()) == 0:
            self.log.error('No one online!')
            return

        return await self.delegate_work_socket_book.send_to_peers(
               msg=tx_batch
           )

        ## SEND OUT VIA SOCKETS CLASS
        # return await secure_multicast(
        #     wallet=self.wallet,
        #     ctx=self.ctx,
        #     msg=tx_batch,
        #     peers=self.dl_wk_sks()
        # )

        # return await multicast(self.ctx, tx_batch, self.delegate_work_sockets())  # Works

    async def wait_for_work(self, block):
        is_skip_block = canonical.block_is_skip_block(block)

        if is_skip_block:
            self.log.info('SKIP. Going to hang now...')

        # If so, hang until you get a new block or some work OR NBN
        self.nbn_inbox.clean()

        while is_skip_block and len(self.tx_batcher.queue) <= 0:
            if len(self.nbn_inbox.q) > 0:
                break

            await asyncio.sleep(0)

    def process_block(self, block):
        #do_not_store = canonical.block_is_failed(block, self.driver.latest_block_hash, self.driver.latest_block_num + 1)
        #do_not_store |= canonical.block_is_skip_block(block)

        self.log.info(f'NEW BLOCK: {block}')

        # if not do_not_store:
        if block['blockNum'] == self.driver.latest_block_num + 1 and block['hash'] != b'\xff' * 32:

            self.driver.update_with_block(block)
            self.issue_rewards(block=block)
            
            self.driver.reads.clear()
            self.driver.pending_writes.clear()
            self.update_sockets()

            # STORE IT IN THE BACKEND
            self.blocks.put(block, self.blocks.BLOCK)
            del block['_id']

            self.store_txs(block)

        self.nbn_inbox.clean()
        self.nbn_inbox.update_signers()
        #self.version_check()

    def store_txs(self, block):
        for subblock in block['subBlocks']:
            for tx in subblock['transactions']:
                self.blocks.put(tx, self.blocks.TX)
                del tx['_id']

    async def process_blocks(self):
        while self.running:
            await self.parameters.refresh()
            self.delegate_work_socket_book.sync_sockets()
            self.nbn_socket_book.sync_sockets()

            sends = await self.send_work()

            if sends is None:
                return

            self.log.error(f'{len(self.contacts.masternodes)} MNS!')

            self.log.info(f'{sends}')

            # this really should just give us a block straight up
            block = await self.aggregator.gather_subblocks(
                total_contacts=len(self.contacts.delegates),
                expected_subblocks=len(self.contacts.masternodes)
            )

            self.process_block(block)

            await self.wait_for_work(block)

            await self.nbn_socket_book.send_to_peers(
                msg=canonical.dict_to_msg_block(block)
            )
            self.version_check()


    def stop(self):
        super().stop()
        self.block_server.stop()
        self.webserver.app.stop()
