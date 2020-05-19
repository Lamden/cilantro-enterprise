import unittest
#import os, pathlib
from cilantro_ee.contracts import sync
from cilantro_ee.cli.utils import build_pepper
from cilantro_ee.crypto.wallet import Wallet
# from contracting.db.driver import ContractDriver
# from contracting.client import ContractingClient
import cilantro_ee
# =============
from unittest import TestCase
from contracting.client import ContractingClient
from contracting.stdlib.bridge.time import Timedelta, DAYS, WEEKS, Datetime
from datetime import datetime as dt, timedelta as td


class TestUpdateContractFix(TestCase):

    def setUp(self):
        self.client = ContractingClient()
        self.mn_wallets = [Wallet().verifying_key().hex() for _ in range(3)]
        self.dn_wallets = [Wallet().verifying_key().hex() for _ in range(3)]
        # Sync contracts
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=self.mn_wallets,
            boot_mns=3,
            initial_delegates=self.dn_wallets,
            boot_dels=3,
            client=self.client
        )

    def tearDown(self):
        self.client.flush()

    def test_init_state(self):
        upgrade = self.client.get_contract('upgrade')
        lock = upgrade.quick_read(variable='upg_lock')
        consensus = upgrade.quick_read(variable='upg_consensus')

        self.assertEqual(lock, False)
        self.assertEqual(consensus, False)

    def test_trigger(self):
        p = build_pepper()
        vk = self.mn_wallets[0]
        upgrade = self.client.get_contract('upgrade')
        upgrade.trigger_upgrade(git_branch_name='dev', pepper=p, initiator_vk=vk)
        state = upgrade.quick_read(variable='upg_lock')
        self.assertEqual(state, True)

    def test_consensys_n_reset(self):
        upgrade = self.client.get_contract('upgrade')
        p = build_pepper()
        br_name = 'ori1-rel-gov-socks'
        upgrade.trigger_upgrade(git_branch_name=br_name, pepper= p, initiator_vk=self.mn_wallets[0])

        upgrade.quick_write(variable='tot_mn', value=3)
        upgrade.quick_write(variable='tot_dl', value=3)
        upgrade.quick_write(variable='mn_vote', value=1)
        upgrade.quick_write(variable='dl_vote', value=2)

        upg_lock = upgrade.quick_read(variable='upg_lock')
        self.assertEqual(upg_lock, True)
        upgrade.vote(vk="tejas")

        master_votes = upgrade.quick_read(variable='mn_vote')
        del_votes = upgrade.quick_read(variable='dl_vote')

        print(master_votes)
        print(del_votes)
        result = upgrade.quick_read(variable='upg_consensus')
        print(result)

        self.assertEqual(result, False)
        upgrade.vote(vk= self.dn_wallets[0])
        upgrade.vote(vk=self.dn_wallets[1])
        master_votes = upgrade.quick_read(variable='mn_vote')
        del_votes = upgrade.quick_read(variable='dl_vote')
        self.assertEqual(master_votes, 1)
        self.assertEqual(del_votes, 4)
        result = upgrade.quick_read(variable='upg_consensus')

        self.assertEqual(result, True)


if __name__ == '__main__':
    unittest.main()
