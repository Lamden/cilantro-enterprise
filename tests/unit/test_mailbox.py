import cilantro_ee.router
import zmq.asyncio
from cilantro_ee.crypto.wallet import Wallet
from unittest import TestCase
import asyncio
from cilantro_ee.router import JSONAsyncInbox


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestAsyncServer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        w = Wallet()
        cilantro_ee.router.AsyncInbox('tcp://127.0.0.1:10000', self.ctx)

    def test_sockets_are_initially_none(self):
        w = Wallet()
        m = cilantro_ee.router.AsyncInbox('tcp://127.0.0.1:10000', self.ctx)

        self.assertIsNone(m.socket)

    def test_setup_frontend_creates_socket(self):
        w = Wallet()
        m = cilantro_ee.router.AsyncInbox('tcp://127.0.0.1:10000', self.ctx)
        m.setup_socket()

        self.assertEqual(m.socket.type, zmq.ROUTER)
        self.assertEqual(m.socket.getsockopt(zmq.LINGER), m.linger)

    def test_sending_message_returns_it(self):
        w = Wallet()
        m = cilantro_ee.router.AsyncInbox('tcp://127.0.0.1:10000', self.ctx, linger=500, poll_timeout=500)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10000')

            await socket.send(msg)

            res = await socket.recv()

            return res

        tasks = asyncio.gather(
            m.serve(),
            get(b'howdy'),
            stop_server(m, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], b'howdy')


class TestJSONAsyncInbox(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        JSONAsyncInbox(socket_id='tcp://127.0.0.1:10000', ctx=self.ctx)

    def test_sockets_are_initially_none(self):
        m = JSONAsyncInbox(socket_id='tcp://127.0.0.1:10000', ctx=self.ctx)

        self.assertIsNone(m.socket)

    def test_setup_frontend_creates_socket(self):
        m = JSONAsyncInbox(socket_id='tcp://127.0.0.1:10000', ctx=self.ctx)
        m.setup_socket()

        self.assertEqual(m.socket.type, zmq.ROUTER)
        self.assertEqual(m.socket.getsockopt(zmq.LINGER), m.linger)

    def test_sending_message_returns_it(self):
        m = JSONAsyncInbox(socket_id='tcp://127.0.0.1:10000', ctx=self.ctx, linger=2000, poll_timeout=50)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10000')

            await socket.send(msg)

            res = await socket.recv()

            return res

        tasks = asyncio.gather(
            m.serve(),
            get(b'{"howdy": "abc"}'),
            stop_server(m, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], b'{"howdy": "abc"}')
