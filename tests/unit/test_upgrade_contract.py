import unittest
import os, pathlib
from cilantro_ee.contracts import sync
from cilantro_ee.cli.utils import build_pepper
from cilantro_ee.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
from cilantro_ee.storage.contract import BlockchainDriver
import cilantro_ee


class TestUpgradeContract(unittest.TestCase):
    def setUp(self):

        self.client = ContractingClient()
        self.driver = BlockchainDriver()


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

    # test if upgrade contract sync's as genesis contract
    def test_upd_sync(self):
        upgrade = self.client.get_contract('upgrade')
        self.assertIsNotNone(upgrade)

    def test_init_state(self):
        upgrade = self.client.get_contract('upgrade')
        lock = upgrade.quick_read(variable='upg_lock')
        consensus = upgrade.quick_read(variable='upg_consensus')

        self.assertEqual(lock, False)
        self.assertEqual(consensus, False)

    def test_check_window(self):
        start_time = self.driver.get_var(contract='upgrade', variable='S', arguments=['init_time'], mark=False)
        current_time = self.driver.get_var(contract='upgrade', variable='S', arguments=['today'], mark=False)
        window = self.driver.get_var(contract='upgrade', variable='S', arguments=['window'], mark=False)

        self.assertEqual(start_time, 0)
        self.assertEqual(current_time, 0)
        self.assertEqual(window, 0)

    def test_trigger(self):
        p = build_pepper()
        vk = self.mn_wallets[1]
        upgrade = self.client.get_contract('upgrade')
        upgrade.trigger_upgrade(pepper=p, initiator_vk=vk)

        state = upgrade.quick_read(variable='upg_lock')
        self.assertEqual(state, True)

        start_time = self.driver.get_var(contract='upgrade', variable='S', arguments=['init_time'], mark=False)
        current_time = self.driver.get_var(contract='upgrade', variable='S', arguments=['today'], mark=False)
        window = self.driver.get_var(contract='upgrade', variable='S', arguments=['window'], mark=False)

        print("{}-{}-{}".format(start_time, current_time, window))

    def test_consensys_n_reset(self):
        upgrade = self.client.get_contract('upgrade')

        upgrade.quick_write(variable='tot_mn', value='3')
        upgrade.quick_write(variable='tot_dl', value='3')
        upgrade.quick_write(variable='mn_vote', value='1')
        upgrade.quick_write(variable='dl_vote', value='2')

        total_mn = upgrade.quick_read(variable='upg_lock')

        upgrade.vote(vk="tejas")

        master_votes = upgrade.quick_read(variable='mn_vote')
        del_votes = upgrade.quick_read(variable='dl_vote')

        print(master_votes)
        print(del_votes)
        result = upgrade.quick_read(variable='upg_consensus')
        print(result)

        self.assertEqual(result, False)
        #
        # upgrade.reset_contract()
        #
        # result = upgrade.quick_read(variable='upg_consensus')
        # self.assertEqual(result, False)


if __name__ == '__main__':
    unittest.main()
