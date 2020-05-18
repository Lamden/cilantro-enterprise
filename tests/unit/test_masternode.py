from cilantro_ee.nodes.masternode import masternode
from cilantro_ee.nodes import base
from cilantro_ee import router, storage, network
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto import canonical
from contracting.db.driver import InMemDriver, ContractDriver
import zmq.asyncio
import asyncio

from unittest import TestCase


def generate_blocks(number_of_blocks, subblocks=[]):
    previous_hash = '0' * 64
    previous_number = 0

    blocks = []
    for i in range(number_of_blocks):
        if len(subblocks) > i:
            subblock = subblocks[i]
        else:
            subblock = []

        new_block = canonical.block_from_subblocks(
            subblocks=subblock,
            previous_hash=previous_hash,
            block_num=previous_number + 1
        )

        blocks.append(new_block)

        previous_hash = new_block['hash']
        previous_number += 1

    return blocks


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestMasternode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_hang_returns_if_not_running(self):
        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key().hex()],
                'delegates': [Wallet().verifying_key().hex()]
            },
            driver=driver
        )

        self.loop.run_until_complete(node.hang())

    def test_hang_until_tx_queue_has_tx(self):
        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key().hex()],
                'delegates': [Wallet().verifying_key().hex()]
            },
            driver=driver
        )

        node.running = True

        async def late_tx(timeout=0.2):
            await asyncio.sleep(timeout)
            node.tx_batcher.queue.append('MOCK TX')

        tasks = asyncio.gather(
            node.hang(),
            late_tx()
        )

        self.loop.run_until_complete(tasks)

    def test_hang_until_nbn_has_block(self):
        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key().hex()],
                'delegates': [Wallet().verifying_key().hex()]
            },
            driver=driver
        )

        node.running = True

        async def late_tx(timeout=0.2):
            await asyncio.sleep(timeout)
            node.new_block_processor.q.append('MOCK BLOCK')

        tasks = asyncio.gather(
            node.hang(),
            late_tx()
        )

        self.loop.run_until_complete(tasks)

    def test_broadcast_new_chain_does_nothing_if_no_tx(self):
        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key().hex()],
                'delegates': [Wallet().verifying_key().hex()]
            },
            driver=driver
        )

        node.client.set_var(
            contract='masternodes',
            variable='S',
            arguments=['members'],
            value=['stu', 'jeff']
        )

    def test_broadcast_new_chain_sends_messages_to_all_peers(self):
        mn_wallet = Wallet()
        mn_bootnode = 'tcp://127.0.0.1:18001'
        mn_router = router.Router(
            wallet=mn_wallet,
            socket_id=mn_bootnode,
            ctx=self.ctx,
            secure=True
        )

        dl_wallet = Wallet()
        dl_bootnode = 'tcp://127.0.0.1:18002'
        dl_router = router.Router(
            wallet=dl_wallet,
            socket_id=dl_bootnode,
            ctx=self.ctx,
            secure=True
        )

        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18003',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [mn_wallet.verifying_key().hex()],
                'delegates': [dl_wallet.verifying_key().hex()]
            },
            driver=driver
        )

        node.client.set_var(
            contract='masternodes',
            variable='S',
            arguments=['members'],
            value=[mn_wallet.verifying_key().hex()]
        )

        node.client.set_var(
            contract='delegates',
            variable='S',
            arguments=['members'],
            value=[dl_wallet.verifying_key().hex()]
        )

        node.socket_authenticator.refresh_governance_sockets()

        node.network.peers = {
            mn_wallet.verifying_key().hex(): mn_bootnode,
            dl_wallet.verifying_key().hex(): dl_bootnode
        }

        node.tx_batcher.queue.append('MOCK TX')

        tasks = asyncio.gather(
            mn_router.serve(),
            dl_router.serve(),
            node.broadcast_new_blockchain_started(),
            stop_server(mn_router, 0.2),
            stop_server(dl_router, 0.2)
        )

        self.loop.run_until_complete(tasks)

    def test_intermediate_catchup_waits_until_key_in_governance(self):
        # A subblock that will have no effect
        sbs_1 = {
            'transactions': [
                {
                    'stamps_used': 100,
                    'state': [
                        {
                            'key': 'currency.balances:jeff',
                            'value': 10000
                        }
                    ],
                    'transaction': {
                        'sender': 'jeff',
                        'nonce': 0,
                        'processor': 'stu'
                    }
                }
            ]
        }

        # A subblock that will add our node to governance
        node_wallet = Wallet()
        sbs_2 = {
            'transactions': [
                {
                    'stamps_used': 100,
                    'state': [
                        {
                            'key': 'masternodes.S:members',
                            'value': [node_wallet.verifying_key().hex()]
                        }
                    ],
                    'transaction': {
                        'sender': 'jeff',
                        'nonce': 1,
                        'processor': 'stu'
                    }
                }
            ]
        }

        blocks = generate_blocks(2, subblocks=[[sbs_1], [sbs_2]])

        driver = ContractDriver(driver=InMemDriver())
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18003',
            ctx=self.ctx,
            wallet=node_wallet,
            constitution={
                'masternodes': [Wallet().verifying_key().hex()],
                'delegates': [Wallet().verifying_key().hex()]
            },
            driver=driver
        )

        async def add_block_late(timeout=1):
            await asyncio.sleep(timeout)
            node.new_block_processor.q.append(blocks[1])

        node.new_block_processor.q.append(blocks[0])
        node.running = True

        tasks = asyncio.gather(
            add_block_late(),
            node.intermediate_catchup(),

        )

        self.loop.run_until_complete(tasks)

        self.assertTrue(node.running)

    def test_intermediate_catchup_stops_if_not_running(self):
        driver = ContractDriver(driver=InMemDriver())
        node_wallet = Wallet()
        node = masternode.Masternode(
            socket_base='tcp://127.0.0.1:18003',
            ctx=self.ctx,
            wallet=node_wallet,
            constitution={
                'masternodes': [Wallet().verifying_key().hex()],
                'delegates': [Wallet().verifying_key().hex()]
            },
            driver=driver
        )

        async def stop_late(timeout=1):
            await asyncio.sleep(timeout)
            node.stop()

        tasks = asyncio.gather(
            stop_late(),
            node.intermediate_catchup(),

        )

        self.loop.run_until_complete(tasks)

        self.assertFalse(node.running)
