from unittest import TestCase
from cilantro_ee.networking.simple_network import *
from cilantro_ee.crypto.wallet import Wallet

from contracting.db.encoder import encode, decode

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
        proof = loop.run_until_complete(i.process_msg({}))

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

        res = self.loop.run_until_complete(j.process_msg(msg))

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

        res = self.loop.run_until_complete(j.process_msg(msg))
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
            j.process_msg(msg)
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
            j.process_msg(msg)
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
            j.process_msg(msg),
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
            ctx=self.ctx
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

