from unittest import TestCase
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet

from cilantro_ee.services.block_fetch import BlockFetcher
from cilantro_ee.services.block_server import BlockServer
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType

from cilantro_ee.storage.master import CilantroStorageDriver

from cilantro_ee.core.top import TopBlockManager
from cilantro_ee.core.sockets import SocketBook

import time
import zmq.asyncio
import zmq
import asyncio
import hashlib
from tests import random_txs


class FakeTopBlockManager:
    def __init__(self, height, hash_):
        self.height = height
        self.hash_ = hash_

    def get_latest_block_hash(self):
        return self.hash_

    def get_latest_block_number(self):
        return self.height


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestBlockFetcher(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.t = TopBlockManager()

    def tearDown(self):
        self.ctx.destroy()
        self.t.driver.flush()

    def test_get_latest_block_height(self):
        w = Wallet()
        m = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10000'),
                        wallet=w,
                        ctx=self.ctx,
                        linger=500,
                        poll_timeout=100,
                        top=FakeTopBlockManager(101, 'abcd'))

        f = BlockFetcher(wallet=Wallet(), ctx=self.ctx)

        tasks = asyncio.gather(
            m.serve(),
            f.get_latest_block_height(services._socket('tcp://127.0.0.1:10000')),
            stop_server(m, 0.1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], 101)

    def test_get_consensus_on_block_height(self):
        w1 = Wallet()
        m1 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10000'),
                         wallet=w1,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'))

        w2 = Wallet()
        m2 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10001'),
                         wallet=w2,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'))

        w3 = Wallet()
        m3 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10002'),
                         wallet=w3,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'))

        w4 = Wallet()
        m4 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10003'),
                         wallet=w4,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(90, 'abcd'))

        class FakeSocketBook:
            def __init__(self, network=None, phonebook_function: callable = None):
                self.network = network
                self.phonebook_function = phonebook_function
                self.sockets = {}

            async def refresh(self):
                self.sockets = self.phonebook_function()

        def get_sockets():
            return {
                'a': services._socket('tcp://127.0.0.1:10000'),
                'b': services._socket('tcp://127.0.0.1:10001'),
                'c': services._socket('tcp://127.0.0.1:10002'),
                'd': services._socket('tcp://127.0.0.1:10003'),
            }

        sock_book = FakeSocketBook(None, get_sockets)

        f = BlockFetcher(wallet=Wallet(), ctx=self.ctx, masternode_sockets=sock_book)

        tasks = asyncio.gather(
            m1.serve(),
            m2.serve(),
            m3.serve(),
            m4.serve(),
            f.find_missing_block_indexes(),
            stop_server(m1, 0.1),
            stop_server(m2, 0.1),
            stop_server(m3, 0.1),
            stop_server(m4, 0.1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[4], 101)