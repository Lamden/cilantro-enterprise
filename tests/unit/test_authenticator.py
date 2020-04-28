from unittest import TestCase
import zmq.asyncio
import asyncio
from cilantro.crypto.wallet import Wallet
from cilantro.sockets.authentication import SocketAuthenticator
import os
from cilantro.storage.vkbook import VKBook
from nacl.signing import SigningKey
from cilantro.contracts import sync
import cilantro
from contracting.client import ContractingClient


class TestAuthenticator(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.w = Wallet()

        masternodes = [Wallet().verifying_key().hex(), Wallet().verifying_key().hex(), Wallet().verifying_key().hex(), ]
        delegates = [Wallet().verifying_key().hex(), Wallet().verifying_key().hex(), Wallet().verifying_key().hex(), ]

        self.c = ContractingClient()
        self.c.flush()

        sync.submit_from_genesis_json_file(cilantro.contracts.__path__[0] + '/genesis.json', client=self.c)
        sync.submit_node_election_contracts(initial_masternodes=masternodes, boot_mns=1,
                                            initial_delegates=delegates, boot_dels=1, client=self.c)

        self.s = SocketAuthenticator(ctx=self.ctx)

    def tearDown(self):
        self.ctx.destroy()

        self.c.flush()

    def test_double_init(self):
        w = Wallet()

        with self.assertRaises(Exception):
            b = SocketAuthenticator(ctx=self.ctx)

    def test_add_verifying_key_as_bytes(self):
        sk = SigningKey.generate()

        self.s.add_verifying_key(sk.verify_key.encode())

        self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{sk.verify_key.encode().hex()}.key')))

    def test_sync_certs_creates_files(self):
        self.s.sync_certs()

        for m in self.s.contacts.masternodes:
            self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{m}.key')))

        for d in self.s.contacts.delegates:
            self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{d}.key')))

    def test_add_governance_sockets_all_creates_files(self):
        fake_mns = [Wallet().verifying_key(), Wallet().verifying_key(), Wallet().verifying_key()]
        fake_od_m = Wallet().verifying_key()

        fake_dels = [Wallet().verifying_key(), Wallet().verifying_key()]
        fake_od_d = Wallet().verifying_key()

        self.s.add_governance_sockets(masternode_list=fake_mns,
                                      on_deck_masternode=fake_od_m,
                                      delegate_list=fake_dels,
                                      on_deck_delegate=fake_od_d
                                      )

        for m in fake_mns:
            self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{m.hex()}.key')))

        for d in fake_dels:
            self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{d.hex()}.key')))

        self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{fake_od_m.hex()}.key')))
        self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{fake_od_d.hex()}.key')))

    # def test_make_client_works(self):
    #     w = Wallet()
    #
    #     pub = self.ctx.socket(zmq.PUB)
    #     pub.curve_secretkey = w.curve_sk
    #     pub.curve_publickey = w.curve_vk
    #
    #     pub.curve_server = True
    #     pub.setsockopt(zmq.LINGER, 1000)
    #     pub.bind('inproc://test1')
    #
    #     self.s.add_verifying_key(w.verifying_key())
    #
    #     sub = self.s.make_client(zmq.SUB, w.verifying_key())
    #
    #     sub.setsockopt(zmq.SUBSCRIBE, b'')
    #     sub.connect('inproc://test1')
    #
    #     async def get():
    #         msg = await sub.recv()
    #         return msg
    #
    #     tasks = asyncio.gather(
    #         pub.send(b'hi'),
    #         get()
    #     )
    #
    #     loop = asyncio.get_event_loop()
    #     _, msg = loop.run_until_complete(tasks)
    #
    #     self.assertEqual(msg, b'hi')
    #
    # def test_make_server_works(self):
    #     w = Wallet()
    #
    #     pub = self.s.make_server(zmq.PUB)
    #     pub.setsockopt(zmq.LINGER, 1000)
    #     pub.bind('inproc://test1')
    #
    #     self.s.add_verifying_key(w.verifying_key())
    #
    #     sub = self.s.make_client(zmq.SUB, w.verifying_key())
    #
    #     sub.setsockopt(zmq.SUBSCRIBE, b'')
    #     sub.connect('inproc://test1')
    #
    #     async def get():
    #         msg = await sub.recv()
    #         return msg
    #
    #     tasks = asyncio.gather(
    #         pub.send(b'hi'),
    #         get()
    #     )
    #
    #     loop = asyncio.get_event_loop()
    #     _, msg = loop.run_until_complete(tasks)
    #
    #     self.assertEqual(msg, b'hi')
