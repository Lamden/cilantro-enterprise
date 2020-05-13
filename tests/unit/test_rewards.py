from unittest import TestCase
from cilantro_ee.nodes import rewards
from contracting.client import ContractingClient
from cilantro_ee.contracts import sync
from contracting.stdlib.bridge.decimal import ContractingDecimal
import cilantro_ee


class TestRewards2(TestCase):
    def setUp(self):
        self.client = ContractingClient()

    def tearDown(self):
        self.client.flush()

    def sync(self):
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=['stu', 'raghu', 'steve'],
            boot_mns=2,
            initial_delegates=['tejas', 'alex'],
            boot_dels=3,
            client=self.client
        )

    def test_contract_exists_false_before_sync(self):
        self.assertFalse(rewards.contract_exists('stamp_cost', self.client))

    def test_contract_exists_true_after_sync(self):
        # Sync contracts
        self.sync()
        self.assertTrue(rewards.contract_exists('stamp_cost', self.client))

    def test_is_setup_false_before_sync(self):
        self.assertFalse(rewards.is_setup(self.client))

    def test_is_setup_true_after_sync(self):
        self.sync()
        self.assertTrue(rewards.is_setup(self.client))

    def test_add_to_balance_if_none_sets(self):
        rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 123)

    def test_add_to_balance_twice_sets_accordingly(self):
        rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 123)

        rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 246)



class TestRewards(TestCase):
    def setUp(self):

        self.client = ContractingClient()
        self.driver = self.client.raw_driver

        # Sync contracts
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=['stu', 'raghu', 'steve'],
            boot_mns=2,
            initial_delegates=['tejas', 'alex'],
            boot_dels=3,
            client=self.client
        )

    def tearDown(self):
        self.client.flush()

    def test_add_rewards(self):
        block = random_txs.random_block()

        total = 0

        for sb in block.subBlocks:
            for tx in sb.transactions:
                total += tx.stampsUsed

        self.assertEqual(self.r.stamps_in_block(block), total)

    def test_add_to_balance(self):
        currency_contract = self.client.get_contract('currency')
        current_balance = currency_contract.quick_read(variable='balances', key='test')

        if current_balance is None:
            current_balance = 0

        self.assertEqual(current_balance, 0)

        rewards.add_to_balance('test', 1234, client=self.client)
        self.client.raw_driver.commit()

        current_balance = currency_contract.quick_read(variable='balances', key='test')
        if current_balance is None:
            current_balance = 0

        self.assertEqual(current_balance, 1234)

        rewards.add_to_balance('test', 1234, client=self.client)
        self.client.raw_driver.commit()

        current_balance = currency_contract.quick_read(variable='balances', key='test')
        if current_balance is None:
            current_balance = 0

        self.assertEqual(current_balance, 2234)

    def test_stamps_per_tau_works(self):
        self.assertEqual(self.r.stamps_per_tau, 20_000)

        stamps = self.client.get_contract('stamp_cost')

        stamps.quick_write('S', 'rate', 555)

        self.assertEqual(self.r.stamps_per_tau, 555)

    def test_reward_ratio_works(self):
        self.assertEqual(self.r.reward_ratio, [0.5, 0.5, 0, 0])

    def test_issue_rewards_works(self):
        self.r.set_pending_rewards(1000)
        self.r.issue_rewards()

        currency_contract = self.client.get_contract('currency')

        self.r.add_to_balance('raghu', 1000)
        self.r.add_to_balance('steve', 10000)

        self.assertEqual(currency_contract.quick_read(variable='balances', key='stu'), ContractingDecimal(166.66666666666666))
        self.assertEqual(currency_contract.quick_read(variable='balances', key='raghu'), ContractingDecimal(1166.66666666666666))
        self.assertEqual(currency_contract.quick_read(variable='balances', key='steve'), ContractingDecimal(10166.66666666666666))

        self.assertEqual(currency_contract.quick_read(variable='balances', key='tejas'), 250)
        self.assertEqual(currency_contract.quick_read(variable='balances', key='alex'), 250)

        self.assertEqual(self.r.get_pending_rewards(), 0)
