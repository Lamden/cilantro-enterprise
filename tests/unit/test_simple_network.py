from unittest import TestCase
from cilantro_ee.network import *
from cilantro_ee.crypto.wallet import Wallet

from contracting.db.encoder import encode, decode
from contracting.client import ContractingClient
from cilantro_ee.router import Router

from cilantro_ee import authentication

import asyncio
import zmq.asyncio


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestProcessors(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.base_tcp = 'tcp://127.0.0.1:19000'
        self.base_wallet = Wallet()

        self.router = Router(socket_id=self.base_tcp, ctx=self.ctx, wallet=self.base_wallet, secure=True)

        self.authenticator = authentication.SocketAuthenticator(client=ContractingClient(), ctx=self.ctx)
        self.authenticator.add_verifying_key(self.base_wallet.verifying_key().hex())
        self.authenticator.configure()

    def tearDown(self):
        self.authenticator.authenticator.stop()
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
            peers={},
            wallet=Wallet()
        )

        res = self.loop.run_until_complete(j.process_message(msg))

        self.assertIsNone(res)

    def test_join_processor_good_message_offline_returns_none(self):
        w = Wallet()

        self.authenticator.add_verifying_key(w.verifying_key().hex())
        self.authenticator.configure()

        msg = {
            'vk': w.verifying_key().hex(),
            'ip': 'tcp://127.0.0.1:18000'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers={},
            wallet=Wallet()
        )

        res = self.loop.run_until_complete(j.process_message(msg))
        self.assertIsNone(res)

    def test_join_processor_good_message_bad_proof_returns_none(self):
        w = Wallet()

        self.authenticator.add_verifying_key(w.verifying_key().hex())
        self.authenticator.configure()

        msg = {
            'vk': w.verifying_key().hex(),
            'ip': 'tcp://127.0.0.1:18000'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers={},
            wallet=Wallet()
        )

        async def get():
            res = await router.secure_request(
                msg={"howdy": 123},
                service=JOIN_SERVICE,
                wallet=w,
                vk=self.base_wallet.verifying_key().hex(),
                ip=self.base_tcp,
                ctx=self.ctx
            )

            return res

        tasks = asyncio.gather(
            get(),
            j.process_message(msg)
        )

        res = self.loop.run_until_complete(tasks)

        self.assertIsNone(res[1])

    def test_join_processor_good_message_adds_to_peers(self):
        # Create a new peer (router and service)
        peer_to_add = Wallet()
        self.authenticator.add_verifying_key(peer_to_add.verifying_key().hex())
        self.authenticator.configure()

        other_router = Router(
            socket_id='tcp://127.0.0.1:18000',
            ctx=self.ctx,
            wallet=peer_to_add,
            secure=True
        )

        i = IdentityProcessor(
            wallet=peer_to_add,
            pepper='cilantroV1',
            ip_string='tcp://127.0.0.1:18000'
        )

        other_router.add_service(IDENTITY_SERVICE, i)
        ###

        peers = {
            self.base_wallet.verifying_key().hex(): 'tcp://127.0.0.1:18001'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers=peers,
            wallet=self.base_wallet
        )

        msg = {
            'vk': peer_to_add.verifying_key().hex(),
            'ip': 'tcp://127.0.0.1:18000'
        }

        tasks = asyncio.gather(
            other_router.serve(),
            j.process_message(msg),
            stop_server(other_router, 1)
        )

        self.loop.run_until_complete(tasks)

        self.assertEqual(peers[peer_to_add.verifying_key().hex()], 'tcp://127.0.0.1:18000')

    def test_join_processor_good_message_forwards_to_peers_and_returns_to_sender(self):
        # JOINER PEER
        peer_to_add = Wallet()
        self.authenticator.add_verifying_key(peer_to_add.verifying_key().hex())
        self.authenticator.configure()

        other_router = Router(
            socket_id='tcp://127.0.0.1:18000',
            ctx=self.ctx,
            wallet=peer_to_add,
            secure=True
        )

        i = IdentityProcessor(
            wallet=peer_to_add,
            pepper='cilantroV1',
            ip_string='tcp://127.0.0.1:18000'
        )

        other_router.add_service(IDENTITY_SERVICE, i)
        ###

        existing_peer = Wallet()
        peers = {
            existing_peer.verifying_key().hex(): 'tcp://127.0.0.1:18001'
        }

        # EXISTING PEER
        self.authenticator.add_verifying_key(existing_peer.verifying_key().hex())
        self.authenticator.configure()

        existing_router = Router(
            socket_id='tcp://127.0.0.1:18001',
            ctx=self.ctx,
            wallet=existing_peer,
            secure=True
        )

        i2 = IdentityProcessor(
            wallet=existing_peer,
            pepper='cilantroV1',
            ip_string='tcp://127.0.0.1:18001'
        )

        j2 = JoinProcessor(
            ctx=self.ctx,
            peers=peers,
            wallet=existing_peer
        )

        existing_router.add_service(IDENTITY_SERVICE, i2)
        existing_router.add_service(JOIN_SERVICE, j2)
        ###

        peers_2 = {
            existing_peer.verifying_key().hex(): 'tcp://127.0.0.1:18001'
        }
        j = JoinProcessor(
            ctx=self.ctx,
            peers=peers_2,
            wallet=self.base_wallet
        )

        msg = {
            'vk': peer_to_add.verifying_key().hex(),
            'ip': 'tcp://127.0.0.1:18000'
        }

        tasks = asyncio.gather(
            other_router.serve(),
            existing_router.serve(),
            j.process_message(msg),
            stop_server(other_router, 1),
            stop_server(existing_router, 1)
        )

        res = self.loop.run_until_complete(tasks)

        # response = decode(res[2])

        expected = {}
        for p in res[2]['peers']:
            expected[p['vk']] = p['ip']

        self.assertDictEqual(peers, expected)
        self.assertDictEqual(peers_2, expected)


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

        real_bootnodes = {
            w_1.verifying_key().hex(): bootnodes[0],
            w_2.verifying_key().hex(): bootnodes[1]
        }

        tasks = asyncio.gather(
            reply(bootnodes[0], peers_1),
            reply(bootnodes[1], peers_2),
            n.start(real_bootnodes, [w_1.verifying_key().hex(), w_2.verifying_key().hex()])
        )

        self.loop.run_until_complete(tasks)

        expected = {
            w_1.verifying_key().hex(): bootnodes[0],
            w_2.verifying_key().hex(): bootnodes[1],
            me.verifying_key().hex(): 'tcp://127.0.0.1:18002'
        }

        self.assertDictEqual(n.peers, expected)

    def test_mock_multiple_networks(self):
        w1 = Wallet()
        w2 = Wallet()
        w3 = Wallet()

        ips = ['tcp://127.0.0.1:18001',
               'tcp://127.0.0.1:18002',
               'tcp://127.0.0.1:18003']

        bootnodes = {
            w1.verifying_key().hex(): ips[0],
            w2.verifying_key().hex(): ips[1],
            w3.verifying_key().hex(): ips[2],
        }

        r1 = Router(
            socket_id=ips[0],
            ctx=self.ctx,
            wallet=w1
        )
        n1 = Network(
            wallet=w1,
            ip_string=ips[0],
            ctx=self.ctx,
            router=r1
        )

        r2 = Router(
            socket_id=ips[1],
            ctx=self.ctx,
            wallet=w1
        )
        n2 = Network(
            wallet=w2,
            ip_string=ips[1],
            ctx=self.ctx,
            router=r2
        )

        r3 = Router(
            socket_id=ips[2],
            ctx=self.ctx,
            wallet=w1
        )
        n3 = Network(
            wallet=w3,
            ip_string=ips[2],
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
