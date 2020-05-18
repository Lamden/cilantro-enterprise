from unittest import TestCase
from cilantro_ee.network import *
from cilantro_ee.crypto.wallet import Wallet

from contracting.db.encoder import encode, decode
from cilantro_ee.router import Router

import asyncio
import zmq.asyncio


class TestProcessors(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_identity_processor_create_proof(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1:9999'
        )

        proof = i.create_proof()

        self.assertTrue(verify_proof(proof, 'test'))

    def test_identity_false_proof_fails(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1:9999'
        )

        proof = i.create_proof()

        proof['signature'] = '0' * 128

        self.assertFalse(verify_proof(proof, 'test'))

    def test_proof_timeout_fails(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1:9999'
        )

        proof = i.create_proof()

        proof['timestamp'] = 0

        self.assertFalse(verify_proof(proof, 'test'))

    def test_process_msg_returns_proof_no_matter_what(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1:9999'
        )

        loop = asyncio.get_event_loop()
        proof = loop.run_until_complete(i.process_message({}))

        self.assertTrue(verify_proof(proof, 'test'))

    def test_join_processor_returns_none_if_message_not_formatted(self):
        msg = {
            'vk': 'bad',
            'ip': 'bad'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers={}
        )

        res = self.loop.run_until_complete(j.process_message(msg))

        self.assertIsNone(res)

    def test_join_processor_good_message_offline_returns_none(self):
        msg = {
            'vk': '0' * 64,
            'ip': 'tcp://127.0.0.1:18000'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers={}
        )

        res = self.loop.run_until_complete(j.process_message(msg))
        self.assertIsNone(res)

    def test_join_processor_good_message_bad_proof_returns_none(self):
        msg = {
            'vk': '0' * 64,
            'ip': 'tcp://127.0.0.1:18000'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers={}
        )

        async def get():
            socket = self.ctx.socket(zmq.ROUTER)
            socket.bind('tcp://127.0.0.1:18000')

            res = await socket.recv_multipart()
            msg = b'{"howdy": 123}'
            await socket.send_multipart(
                [res[0], msg]
            )

            return res

        tasks = asyncio.gather(
            get(),
            j.process_message(msg)
        )

        res = self.loop.run_until_complete(tasks)

        self.assertIsNone(res[1])

    def test_join_processor_good_message_adds_to_peers(self):
        peer_to_add = Wallet()
        i = IdentityProcessor(
            wallet=peer_to_add,
            pepper='cilantroV1',
            ip_string='tcp://127.0.0.1:18000'
        )

        peers = {
            'f' * 64: 'tcp://127.0.0.1:18001'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers=peers
        )

        async def get():
            socket = self.ctx.socket(zmq.ROUTER)
            socket.bind('tcp://127.0.0.1:18000')

            res = await socket.recv_multipart()
            msg = encode(i.create_proof()).encode()
            await socket.send_multipart(
                [res[0], msg]
            )

            return res

        msg = {
            'vk': peer_to_add.verifying_key().hex(),
            'ip': 'tcp://127.0.0.1:18000'
        }

        tasks = asyncio.gather(
            get(),
            j.process_message(msg)
        )

        self.loop.run_until_complete(tasks)

        self.assertEqual(peers[peer_to_add.verifying_key().hex()], 'tcp://127.0.0.1:18000')

    def test_join_processor_good_message_forwards_to_peers_and_returns_to_sender(self):
        peer_to_add = Wallet()
        i = IdentityProcessor(
            wallet=peer_to_add,
            pepper='cilantroV1',
            ip_string='tcp://127.0.0.1:18000'
        )

        peers = {
            'f' * 64: 'tcp://127.0.0.1:18001'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers=peers
        )

        # Joiner
        async def get():
            socket = self.ctx.socket(zmq.ROUTER)
            socket.bind('tcp://127.0.0.1:18000')

            res = await socket.recv_multipart()
            msg = encode(i.create_proof()).encode()
            await socket.send_multipart(
                [res[0], msg]
            )

            return res

        # Existing Peer
        async def reply():
            socket = self.ctx.socket(zmq.ROUTER)
            socket.bind('tcp://127.0.0.1:18001')

            res = await socket.recv_multipart()
            await socket.send_multipart(
                [res[0], b'{}']
            )

            return res[1]

        msg = {
            'vk': peer_to_add.verifying_key().hex(),
            'ip': 'tcp://127.0.0.1:18000'
        }

        tasks = asyncio.gather(
            get(),
            j.process_message(msg),
            reply()
        )

        res = self.loop.run_until_complete(tasks)

        response = decode(res[-1])

        expected = {
            'service': 'join',
            'msg': msg
        }

        self.assertDictEqual(response, expected)

        expected_return = {
            'peers': peers
        }

        self.assertDictEqual(res[1], expected_return)


class TestNetwork(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_start_sends_joins_and_adds_peers_that_respond(self):
        me = Wallet()
        n = Network(
            wallet=me,
            ip_string='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            router=Router(
                socket_id='tcp://127.0.0.1:18002',
                ctx=self.ctx
            )
        )

        bootnodes = [
            'tcp://127.0.0.1:18003',
            'tcp://127.0.0.1:18004'
        ]

        async def reply(tcp, peers):
            socket = self.ctx.socket(zmq.ROUTER)
            socket.bind(tcp)

            res = await socket.recv_multipart()
            await socket.send_multipart(
                [res[0], encode(peers).encode()]
            )

            return res[1]

        w_1 = Wallet()
        peers_1 = {
            'peers': [{'vk': w_1.verifying_key().hex(), 'ip': bootnodes[0]}]
        }

        w_2 = Wallet()
        peers_2 = {
            'peers': [{'vk': w_2.verifying_key().hex(), 'ip': bootnodes[1]}]
        }

        tasks = asyncio.gather(
            reply(bootnodes[0], peers_1),
            reply(bootnodes[1], peers_2),
            n.start(bootnodes, [w_1.verifying_key().hex(), w_2.verifying_key().hex()])
        )

        self.loop.run_until_complete(tasks)

        expected = {
            w_1.verifying_key().hex(): bootnodes[0],
            w_2.verifying_key().hex(): bootnodes[1],
            me.verifying_key().hex(): 'tcp://127.0.0.1:18002'
        }

        self.assertDictEqual(n.peers, expected)

    def test_mock_multiple_networks(self):
        bootnodes = ['tcp://127.0.0.1:18001',
                     'tcp://127.0.0.1:18002',
                     'tcp://127.0.0.1:18003']

        w1 = Wallet()
        r1 = Router(
            socket_id=bootnodes[0],
            ctx=self.ctx,
            wallet=w1
        )
        n1 = Network(
            wallet=w1,
            ip_string=bootnodes[0],
            ctx=self.ctx,
            router=r1
        )

        w2 = Wallet()
        r2 = Router(
            socket_id=bootnodes[1],
            ctx=self.ctx,
            wallet=w1
        )
        n2 = Network(
            wallet=w2,
            ip_string=bootnodes[1],
            ctx=self.ctx,
            router=r2
        )

        w3 = Wallet()
        r3 = Router(
            socket_id=bootnodes[2],
            ctx=self.ctx,
            wallet=w1
        )
        n3 = Network(
            wallet=w3,
            ip_string=bootnodes[2],
            ctx=self.ctx,
            router=r3
        )

        vks = [w1.verifying_key().hex(),
               w2.verifying_key().hex(),
               w3.verifying_key().hex()]

        async def stop_server(s: Router, timeout=0.2):
            await asyncio.sleep(timeout)
            s.stop()

        tasks = asyncio.gather(
            r1.serve(),
            r2.serve(),
            r3.serve(),
            n1.start(bootnodes, vks),
            n2.start(bootnodes, vks),
            n3.start(bootnodes, vks),
            stop_server(r1),
            stop_server(r2),
            stop_server(r3),
        )

        self.loop.run_until_complete(tasks)

        expected = {
            w1.verifying_key().hex(): bootnodes[0],
            w2.verifying_key().hex(): bootnodes[1],
            w3.verifying_key().hex(): bootnodes[2],
        }

        self.assertDictEqual(n1.peers, expected)
        self.assertDictEqual(n2.peers, expected)
        self.assertDictEqual(n3.peers, expected)
