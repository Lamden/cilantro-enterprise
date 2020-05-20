from unittest import TestCase
from cilantro_ee.router import Router, QueueProcessor, OK, Processor
import zmq.asyncio
import asyncio
from contracting.db.encoder import encode, decode


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestRouter(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_add_service(self):
        r = Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)
        q = QueueProcessor()

        r.add_service('test', q)

        self.assertEqual(r.services['test'], q)

    def test_inbox_none_returns_default_message(self):
        r = Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        bad_message = {
            'blah': 123
        }

        tasks = asyncio.gather(
            r.serve(),
            request(bad_message),
            stop_server(r, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], OK)

    def test_request_none_returns_default_message(self):
        r = Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        bad_message = {
            'service': 'hello',
            'blah': 123
        }

        tasks = asyncio.gather(
            r.serve(),
            request(bad_message),
            stop_server(r, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], OK)

    def test_no_processor_returns_default_message(self):
        r = Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        bad_message = {
            'service': 'hello',
            'msg': {
                'hello': 123
            }
        }

        tasks = asyncio.gather(
            r.serve(),
            request(bad_message),
            stop_server(r, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], OK)

    def test_queue_processor_returns_default_message(self):
        r = Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)
        q = QueueProcessor()

        r.add_service('test', q)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        message = {
            'service': 'test',
            'msg': {
                'howdy': 'there'
            }
        }

        expected_q = [{
                'howdy': 'there'
            }]

        tasks = asyncio.gather(
            r.serve(),
            request(message),
            stop_server(r, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], OK)
        self.assertListEqual(expected_q, q.q)

    def test_mock_processor_returns_custom_message(self):
        r = Router(socket_id='ipc:///tmp/router', ctx=self.ctx, linger=50)

        class MockProcessor(Processor):
            async def process_message(self, msg):
                return {
                    'whats': 'good'
                }

        q = MockProcessor()

        r.add_service('test', q)

        async def request(msg):
            msg = encode(msg).encode()

            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('ipc:///tmp/router')

            await socket.send(msg)

            resp = await socket.recv()

            resp = decode(resp)

            return resp

        message = {
            'service': 'test',
            'msg': {
                'howdy': 'there'
            }
        }

        expected_msg = {
                    'whats': 'good'
                }

        tasks = asyncio.gather(
            r.serve(),
            request(message),
            stop_server(r, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertDictEqual(res[1], expected_msg)
