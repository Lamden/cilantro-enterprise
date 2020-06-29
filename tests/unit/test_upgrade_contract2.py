import unittest
import os
from cilantro_ee.contracts import sync
from cilantro_ee.cli.utils import build_pepper, get_version
from cilantro_ee.crypto.wallet import Wallet
import cilantro_ee
from unittest import TestCase
from contracting.client import ContractingClient


class TestUpdateContractFix(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.client.flush()

        self.mn_wallets = [Wallet().verifying_key for _ in range(3)]
        self.dn_wallets = [Wallet().verifying_key for _ in range(3)]

        # Sync contracts
        sync.setup_genesis_contracts(
            initial_masternodes=self.mn_wallets,
            initial_delegates=self.dn_wallets,
            client=self.client,
            filename=cilantro_ee.contracts.__path__[0] + '/genesis.json',
            root=cilantro_ee.contracts.__path__[0]
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
        upgrade.trigger_upgrade(cilantro_branch_name='dev', pepper=p, initiator_vk=vk)
        state = upgrade.quick_read(variable='upg_lock')

        self.assertEqual(state, True)

    def test_consensys_n_reset(self):
        upgrade = self.client.get_contract('upgrade')
        p = build_pepper()
        br_name = 'ori1-rel-gov-socks'

        upgrade.trigger_upgrade(cilantro_branch_name=br_name, contract_branch_name=br_name, pepper= p, initiator_vk=self.mn_wallets[0])

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
        br_name_contract = upgrade.quick_read(variable='branch_name')
        self.assertEqual(br_name, br_name_contract)
        self.assertEqual(master_votes, 1)
        self.assertEqual(del_votes, 4)
        result = upgrade.quick_read(variable='upg_consensus')

        self.assertEqual(result, True)

    def test_build_pepper(self):
        p = build_pepper()
        self.assertEqual(p, p)

    def test_git_branch(self):
        path = os.path.join( os.path.dirname(cilantro_ee.__file__), '..')
        os.chdir(path)

        new_branch_name=None
        # subprocess.check_call(['git', "rev-parse", "--abbrev", "-ref", "HEAD"])  # git rev-parse --abbrev-ref HEAD
        from subprocess import check_output
        new_branch_name = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).rstrip().decode()
        print (new_branch_name)
        old_branch = get_version()
        flag = 'ori1-rel-gov-socks-upg' == old_branch
        print(flag)

if __name__ == '__main__':
    unittest.main()
