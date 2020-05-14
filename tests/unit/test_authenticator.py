from unittest import TestCase
import zmq.asyncio
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.authentication import SocketAuthenticator
import os
from nacl.signing import SigningKey
from cilantro_ee.contracts import sync
import cilantro_ee
from contracting.client import ContractingClient


class TestAuthenticator(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.w = Wallet()

        masternodes = [Wallet().verifying_key().hex(), Wallet().verifying_key().hex(), Wallet().verifying_key().hex(), ]
        delegates = [Wallet().verifying_key().hex(), Wallet().verifying_key().hex(), Wallet().verifying_key().hex(), ]

        self.c = ContractingClient()
        self.c.flush()

        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json', client=self.c)
        sync.submit_node_election_contracts(initial_masternodes=masternodes, boot_mns=1,
                                            initial_delegates=delegates, boot_dels=1, client=self.c)

        self.s = SocketAuthenticator(ctx=self.ctx)

    def tearDown(self):
        self.ctx.destroy()

        self.c.flush()

    def test_add_verifying_key_writes_file(self):
        sk = SigningKey.generate()

        self.s.add_verifying_key(sk.verify_key.encode().hex())

        self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{sk.verify_key.encode().hex()}.key')))

    def test_add_verifying_key_invalid_does_nothing(self):
        sk = b'\x00' * 32

        self.s.add_verifying_key(sk.hex())

        self.assertFalse(os.path.exists(os.path.join(self.s.cert_dir, f'{sk.hex()}.key')))

    def test_add_governance_sockets_all_creates_files(self):
        fake_mns = [
            Wallet().verifying_key().hex(),
            Wallet().verifying_key().hex(),
            Wallet().verifying_key().hex()
        ]

        fake_od_m = Wallet().verifying_key().hex()

        fake_dels = [
            Wallet().verifying_key().hex(),
            Wallet().verifying_key().hex()
        ]

        fake_od_d = Wallet().verifying_key().hex()

        self.s.refresh_governance_sockets(masternode_list=fake_mns,
                                          on_deck_masternode=fake_od_m,
                                          delegate_list=fake_dels,
                                          on_deck_delegate=fake_od_d
                                          )

        for m in fake_mns:
            self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{m}.key')))

        for d in fake_dels:
            self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{d}.key')))

        self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{fake_od_m}.key')))
        self.assertTrue(os.path.exists(os.path.join(self.s.cert_dir, f'{fake_od_d}.key')))
