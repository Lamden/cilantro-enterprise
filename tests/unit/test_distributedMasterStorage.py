from unittest import TestCase
from cilantro.storage.master import DistributedMasterStorage
from cilantro.crypto.wallet import Wallet
from cilantro.storage.vkbook import VKBook
from cilantro.contracts import sync
import cilantro
from contracting.client import ContractingClient


class TestDistributedMasterStorage(TestCase):
    def setUp(self):
        #m, d = sync.get_masternodes_and_delegates_from_constitution()
        self.client = ContractingClient()
        self.client.flush()
        sync.submit_from_genesis_json_file(cilantro.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=Wallet().verifying_key().hex(),
            boot_mns=1,
            initial_delegates=Wallet().verifying_key().hex(),
            boot_dels=1,
            client=self.client
        )

        w = Wallet()
        sk, vk = w.signing_key(), w.verifying_key()
        self.db = DistributedMasterStorage(key=sk, vkbook=VKBook(self.client, 1, 1))

    def tearDown(self):
        self.db.drop_collections()

    def test_init(self):
        self.assertTrue(self.db)

    def test_get_masterset_test_hook_false(self):
        self.db.test_hook = False

        self.assertEqual(len(self.db.vkbook.masternodes), self.db.get_master_set())

    def test_get_masterset_test_hook_true(self):
        am = self.db.active_masters

        self.db.test_hook = True

        self.assertEqual(am, self.db.get_master_set())

    def test_set_mn_id_test_hook_true(self):
        mn_id = self.db.mn_id

        self.db.test_hook = True

        self.assertEqual(mn_id, self.db.set_mn_id(vk='0'))

    def test_set_mn_id_test_hook_false_master_not_in_active_masters(self):
        vk = 'IMPOSSIBLE WALLET'

        self.db.test_hook = False

        success = self.db.set_mn_id(vk)

        self.assertEqual(self.db.mn_id, -1)
        self.assertFalse(success)

    def test_set_mn_id_test_hook_false_master_in_active_masters(self):
        PhoneBook = VKBook(self.client)

        vk = PhoneBook.masternodes[0]

        self.db.test_hook = False

        success = self.db.set_mn_id(vk)

        self.assertEqual(self.db.mn_id, 0)
        self.assertTrue(success)

    def test_rep_pool_size_fails_when_active_masters_less_than_rep_factor(self):
        self.db.rep_factor = 999
        self.assertEqual(self.db.rep_pool_sz(), -1)

    def test_rep_pool_size_returns_correctly_rounded_pool_size_when_enough_masters_present(self):
        self.db.test_hook = True

        self.db.rep_factor = 1
        pool = round(self.db.active_masters / self.db.rep_factor)
        self.assertEqual(self.db.rep_pool_sz(), pool)

    def test_build_write_list_returns_all_mns_when_jump_idx_0(self):
        PhoneBook = VKBook(self.client)

        mns = PhoneBook.masternodes

        self.assertEqual(mns, self.db.build_wr_list(None, 0))

    def test_build_write_list_curr_node_0_jump_idx_1_returns_all(self):
        masternodes = list(range(100))
        delegates = list(range(10))

        self.client.flush()
        sync.submit_from_genesis_json_file(cilantro.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=masternodes,
            boot_mns=1,
            initial_delegates=delegates,
            boot_dels=1,
            client=self.client
        )

        big_vkbook = VKBook(self.client)

        self.db.vkbook = big_vkbook

        write_list = self.db.build_wr_list(0, 1)
        self.assertEqual(masternodes, write_list)

    def test_build_write_list_curr_node_20_jump_idx_1_returns_subset(self):
        masternodes = list(range(100))
        delegates = list(range(10))

        self.client.flush()
        sync.submit_from_genesis_json_file(cilantro.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=masternodes,
            boot_mns=1,
            initial_delegates=delegates,
            boot_dels=1,
            client=self.client
        )

        big_vkbook = VKBook(self.client)

        self.db.vkbook = big_vkbook

        write_list = self.db.build_wr_list(20, 1)
        self.assertEqual(masternodes[20:], write_list)

    def test_update_index(self):
        block = {
            'blockNum': 100,
            'hash': 'a',
            'data': 'woohoo'
        }

        owners = ['tejas', 'stu']

        self.db.update_index(block, owners)

        stored_index = self.db.get_index(100)

        self.assertEqual(stored_index['blockOwners'], owners)

    def test_update_index_no_owners(self):
        block = {
            'blockNum': 100,
            'hash': 'a',
            'data': 'woohoo'
        }

        with self.assertRaises(AssertionError):
            self.db.update_index(block, [])

    def test_update_index_no_block_hash(self):
        block = {
            'blockNum': 100,
            'data': 'woohoo'
        }

        with self.assertRaises(AssertionError):
            self.db.update_index(block, ['tejas', 'stu'])

    def test_update_index_fails_with_no_block_num(self):
        block = {
            'hash': 'a',
            'data': 'woohoo'
        }

        with self.assertRaises(AssertionError):
            self.db.update_index(block, ['tejas', 'stu'])

    def test_build_write_list_jump_idx_2_skips(self):
        masternodes = list(range(100))
        delegates = list(range(10))

        self.client.flush()
        sync.submit_from_genesis_json_file(cilantro.contracts.__path__[0] + '/genesis.json', client=self.client)
        sync.submit_node_election_contracts(
            initial_masternodes=masternodes,
            boot_mns=1,
            initial_delegates=delegates,
            boot_dels=1,
            client=self.client
        )

        big_vkbook = VKBook(self.client)

        self.db.vkbook = big_vkbook

        write_list = self.db.build_wr_list(20, 2)
        self.assertEqual(masternodes[20::2], write_list)

    def test_evaluate_write_no_entry_returns_false(self):
        self.assertFalse(self.db.evaluate_wr())

    def test_evaluate_write_always_write_if_too_few_masters(self):
        self.db.active_masters = 1
        self.db.quorum_needed = 4

        block = {
            'blockNum': 103,
            'hash': 'a',
            'data': 'woohoo'
        }

        self.db.evaluate_wr(block)

        stored_block = self.db.get_block(103)

        block.pop('_id')

        self.assertEqual(stored_block, block)

        stored_index = self.db.get_index(103)

        owners = self.db.build_wr_list(self.db.mn_id, 0)

        self.assertEqual(stored_index['blockOwners'], owners)
        self.assertEqual(stored_index['hash'], block['hash'])
        self.assertEqual(stored_index['blockNum'], block['blockNum'])

    def test_eval_write_node_id_is_in_writers_returns_true(self):
        self.db.rep_factor = 1

        block = {
            'blockNum': 100,
            'hash': 'a',
            'data': 'woohoo'
        }

        res = self.db.evaluate_wr(block, node_id=0)

        self.assertTrue(res)

    def test_eval_write_node_id_is_not_in_writers_returns_false(self):
        self.db.rep_factor = 1

        block = {
            'blockNum': 100,
            'hash': 'a',
            'data': 'woohoo'
        }

        res = self.db.evaluate_wr(block, node_id=1)

        self.assertFalse(res)

    def test_eval_write_if_mn_is_writer_then_write_block(self):
        self.db.rep_factor = 1

        block = {
            'blockNum': 100,
            'hash': 'a',
            'data': 'woohoo'
        }

        self.db.evaluate_wr(block)

        stored_block = self.db.get_block(100)
        stored_index = self.db.get_index(100)

        self.assertEqual(block, stored_block)

        self.assertEqual(stored_index['hash'], block['hash'])
        self.assertEqual(stored_index['blockNum'], block['blockNum'])

    def test_get_full_block_by_number(self):

        block = {
            'blockNum': 100,
            'hash': 'a',
            'data': 'woohoo'
        }

        self.db.put(block, DistributedMasterStorage.BLOCK)

        block.pop('_id')

        stored_block = self.db.get_block(100)

        self.assertEqual(block, stored_block)

    def test_get_full_block_by_hash(self):
        block = {
            'blockNum': 101,
            'hash': 'abcdef',
            'data': 'woohoo'
        }

        self.db.blocks.insert_one(block)

        block.pop('_id')

        stored_block = self.db.get_block('abcdef')

        self.assertEqual(block, stored_block)

    def test_get_full_block_returns_none_if_nothing_provided(self):
        self.assertIsNone(self.db.get_block())
