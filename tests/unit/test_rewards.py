from unittest import TestCase
from cilantro_ee import rewards
from contracting.client import ContractingClient
from cilantro_ee.contracts import sync
import cilantro_ee


class TestRewards(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.rewards = rewards.RewardManager()

    def tearDown(self):
        self.client.flush()

    def sync(self):
        sync.setup_genesis_contracts(['stu', 'raghu', 'steve'], ['tejas', 'alex'], client=self.client)

    def test_contract_exists_false_before_sync(self):
        self.assertFalse(self.rewards.contract_exists('stamp_cost', self.client))

    def test_contract_exists_true_after_sync(self):
        # Sync contracts
        self.sync()
        self.assertTrue(self.rewards.contract_exists('stamp_cost', self.client))

    def test_is_setup_false_before_sync(self):
        self.assertFalse(self.rewards.is_setup(self.client))

    def test_is_setup_true_after_sync(self):
        self.sync()
        self.assertTrue(self.rewards.is_setup(self.client))

    def test_add_to_balance_if_none_sets(self):
        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 123)

    def test_add_to_balance_twice_sets_accordingly(self):
        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 123)

        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 246)

    def test_calculate_rewards_returns_accurate_amounts_per_participant_group(self):
        self.sync()
        self.client.set_var(
            contract='rewards',
            variable='S',
            arguments=['value'],
            value=[0.4, 0.4, 0.1, 0.1]
        )

        total_tau_to_split = 4900

        m, d, f = self.rewards.calculate_all_rewards(total_tau_to_split, self.client)

        reconstructed = (m * 3) + (d * 2) + (f * 1) + (f * 1)

        self.assertAlmostEqual(reconstructed, total_tau_to_split)

    def test_calculate_participant_reward_shaves_off_dust(self):
        rounded_reward = self.rewards.calculate_participant_reward(
            participant_ratio=1,
            number_of_participants=1,
            total_tau_to_split=1.0000000000001
        )

        self.assertEqual(rounded_reward, 1)

    def test_distribute_rewards_adds_to_all_wallets(self):
        self.sync()
        self.client.set_var(
            contract='rewards',
            variable='S',
            arguments=['value'],
            value=[0.4, 0.4, 0.1, 0.1]
        )
        self.client.set_var(
            contract='foundation',
            variable='owner',
            value='xxx'
        )

        total_tau_to_split = 4900

        m, d, f = self.rewards.calculate_all_rewards(total_tau_to_split, self.client)

        self.rewards.distribute_rewards(m, d, f, self.client)

        masters = self.client.get_var(contract='masternodes', variable='S', arguments=['members'])
        delegates = self.client.get_var(contract='delegates', variable='S', arguments=['members'])

        for mn in masters:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[mn], mark=False)
            self.assertEqual(current_balance, m)

        for dl in delegates:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[dl], mark=False)
            self.assertEqual(current_balance, d)

        current_balance = self.client.get_var(contract='currency', variable='balances', arguments=['xxx'], mark=False)
        self.assertEqual(current_balance, f)

    def test_stamps_in_block(self):
        block = {
            'subblocks': [
                {
                    'transactions': [
                        {
                            'stamps_used': 1000
                        },
                        {
                            'stamps_used': 2000
                        },
                        {
                            'stamps_used': 3000
                        }
                    ]
                },

                {
                    'transactions': [
                        {
                            'stamps_used': 4500
                        },
                        {
                            'stamps_used': 1250
                        },
                        {
                            'stamps_used': 2750
                        }
                    ]
                }
            ]
        }

        self.assertEqual(self.rewards.stamps_in_block(block), 14500)

    def test_issue_rewards_full_loop_works(self):
        self.sync()
        self.client.set_var(
            contract='rewards',
            variable='S',
            arguments=['value'],
            value=[0.4, 0.4, 0.1, 0.1]
        )
        self.client.set_var(
            contract='foundation',
            variable='owner',
            value='xxx'
        )
        self.client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=100
        )

        block = {
            'subblocks': [
                {
                    'transactions': [
                        {
                            'stamps_used': 1000
                        },
                        {
                            'stamps_used': 2000
                        },
                        {
                            'stamps_used': 3000
                        }
                    ]
                },

                {
                    'transactions': [
                        {
                            'stamps_used': 4500
                        },
                        {
                            'stamps_used': 1250
                        },
                        {
                            'stamps_used': 2750
                        }
                    ]
                }
            ]
        }

        # tau to distribute should be 145

        tau = self.rewards.calculate_tau_to_split(block, client=self.client)

        self.assertEqual(tau, 145)

        self.rewards.issue_rewards(block, client=self.client)

        total_tau_to_split = 145

        m, d, f = self.rewards.calculate_all_rewards(total_tau_to_split, self.client)

        masters = self.client.get_var(contract='masternodes', variable='S', arguments=['members'])
        delegates = self.client.get_var(contract='delegates', variable='S', arguments=['members'])

        for mn in masters:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[mn], mark=False)
            self.assertEqual(current_balance, m)

        for dl in delegates:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[dl], mark=False)
            self.assertEqual(current_balance, d)

        current_balance = self.client.get_var(contract='currency', variable='balances', arguments=['xxx'], mark=False)
        self.assertEqual(current_balance, f)

