from unittest import TestCase

from cilantro_ee.nodes.masternode.contender.contender import BlockContender, SubBlockContender, PotentialSolution, Aggregator
import zmq.asyncio
import asyncio
from cilantro_ee.sockets.struct import _socket
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.crypto import canonical
import secrets
from cilantro_ee.crypto.wallet import Wallet


class MockContenders:
    def __init__(self, c):
        self.contenders = c


class MockTx:
    def __init__(self):
        self.tx = secrets.token_hex(6)

    def to_dict(self):
        return self.tx


class MockMerkle:
    def __init__(self, leaves):
        self.leaves = leaves
        self.signature = secrets.token_hex(8)

    def to_dict(self):
        return {
            'leaves': self.leaves,
            'signature': self.signature
        }

class MockSBC:
    def __init__(self, input, result, index):
        self.inputHash = input
        self.merkleTree = MockMerkle([result])
        self.subBlockNum = index
        self.signer = secrets.token_hex(8)
        self.transactions = [MockTx() for _ in range(12)]
        self.prevBlockHash = 0

    def to_dict(self):
        return {
            'input_hash': self.inputHash,
            'merkle_tree': self.merkleTree.to_dict(),
            'subblock': self.subBlockNum,
            'signer': self.signer,
            'transactions': [],
            'previous': secrets.token_hex(8)
        }


class TestCurrentContenders(TestCase):
    def test_adding_same_input_and_result_adds_to_the_set(self):
        # Input: 2 blocks

        a = MockSBC(1, 2, 3).to_dict()
        b = MockSBC(1, 2, 3).to_dict()

        c = [a, b]

        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        sb = con.subblock_contenders[3]

        self.assertEqual(sb.potential_solutions[2].votes, 2)

    def test_adding_sbcs_updates_top_vote_initially(self):
        # Input: 2 blocks with different input hashes

        a = MockSBC(1, 2, 1).to_dict()
        b = MockSBC(2, 2, 3).to_dict()

        c = [a, b]

        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)

    def test_adding_sbcs_doesnt_update_if_not_new_result_different(self):
        # Input: 2 blocks with different result hashes, but same input and index

        # Check: votes for each potential solution is 1

        # Input: 2 blocks with more different results
        # Check; votes for the first two potential solutions is still one
        a = MockSBC(input=1, result=2, index=1).to_dict()
        b = MockSBC(input=2, result=2, index=3).to_dict()

        c = [a, b]

        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        a = MockSBC(input=1, result=3, index=1).to_dict()
        b = MockSBC(input=2, result=3, index=3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

    def test_adding_sbcs_increments_top_vote_if_new_result_multiple_and_more_than_previous_top_vote(self):
        a = MockSBC(input=1, result=2, index=1).to_dict()
        b = MockSBC(input=2, result=2, index=3).to_dict()

        c = [a, b]

        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        a = MockSBC(input=1, result=3, index=1).to_dict()
        b = MockSBC(input=2, result=3, index=3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        a = MockSBC(input=1, result=2, index=1).to_dict()
        b = MockSBC(input=2, result=2, index=3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 2)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 2)

    def test_blocks_added_to_finished_when_quorum_met(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1).to_dict()
        b = MockSBC(input=2, result=2, index=3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertFalse(con.block_has_consensus())

        a = MockSBC(1, 1, 1).to_dict()
        b = MockSBC(2, 2, 3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertTrue(con.subblock_contenders[3].has_required_consensus)

    def test_out_of_range_index_not_added(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1).to_dict()
        b = MockSBC(input=2, result=2, index=300).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.current_responded_sbcs(), 1)

    def test_subblock_has_consensus_false_if_not_quorum(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1).to_dict()

        c = [a]

        con.add_sbcs(c)

        self.assertFalse(con.subblock_contenders[1].has_required_consensus)

    def test_block_true_if_all_blocks_have_consensus(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1).to_dict()
        b = MockSBC(input=1, result=2, index=1).to_dict()

        c = MockSBC(input=1, result=2, index=2).to_dict()
        d = MockSBC(input=1, result=2, index=2).to_dict()

        e = MockSBC(input=1, result=2, index=3).to_dict()
        f = MockSBC(input=1, result=2, index=3).to_dict()

        g = MockSBC(input=1, result=2, index=0).to_dict()
        h = MockSBC(input=1, result=2, index=0).to_dict()

        con.add_sbcs([a, b, c, d, e, f, g, h])

        self.assertTrue(con.block_has_consensus())

    def test_block_false_if_one_subblocks_doesnt_have_consensus(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1).to_dict()
        b = MockSBC(input=1, result=2, index=1).to_dict()

        c = MockSBC(input=1, result=2, index=2).to_dict()
        d = MockSBC(input=1, result=2, index=2).to_dict()

        e = MockSBC(input=1, result=2, index=3).to_dict()
        # f = MockSBC(input=1, result=2, index=3)

        g = MockSBC(input=1, result=2, index=0).to_dict()
        h = MockSBC(input=1, result=2, index=0).to_dict()

        con.add_sbcs([a, b, c, d, e, g, h])

        self.assertFalse(con.block_has_consensus())

    def test_block_false_if_one_subblock_is_none(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1).to_dict()
        b = MockSBC(input=1, result=2, index=1).to_dict()

        c = MockSBC(input=1, result=2, index=2).to_dict()
        d = MockSBC(input=1, result=2, index=2).to_dict()

        # e = MockSBC(input=1, result=2, index=3)
        # f = MockSBC(input=1, result=2, index=3)

        g = MockSBC(input=1, result=2, index=0).to_dict()
        h = MockSBC(input=1, result=2, index=0).to_dict()

        con.add_sbcs([a, b, c, d, g, h])

        self.assertFalse(con.block_has_consensus())
    # def test_none_added_if_quorum_cannot_be_reached(self):
    #     con = CurrentContenders(3)
    #
    #     a = MockSBC(1, 2, 1)
    #
    #     con.add_sbcs([a])
    #
    #     self.assertDictEqual(con.finished, {})
    #
    #     b = MockSBC(1, 3, 1)
    #
    #     con.add_sbcs([b])
    #
    #     self.assertDictEqual(con.finished, {})
    #
    #     aa = MockSBC(1, 4, 1)
    #
    #     con.add_sbcs([aa])
    #
    #     self.assertDictEqual(con.finished, {1: None})



class TestAggregator(TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def test_gather_subblocks_all_same_blocks(self):
        a = Aggregator(wallet=Wallet(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

        c1 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c2 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c3 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c4 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertEqual(res['subblocks'][0]['merkle_leaves'][0], 'res_1')
        self.assertEqual(res['subblocks'][1]['merkle_leaves'][0], 'res_2')
        self.assertEqual(res['subblocks'][2]['merkle_leaves'][0], 'res_3')
        self.assertEqual(res['subblocks'][3]['merkle_leaves'][0], 'res_4')

    def test_mixed_results_still_makes_quorum(self):
        a = Aggregator(wallet=Wallet(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

        c1 = [MockSBC('input_1', 'res_X', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c2 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_X', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c3 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_i', 'res_X', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c4 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_X', 3).to_dict()]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertEqual(res['subblocks'][0]['merkle_leaves'][0], 'res_1')
        self.assertEqual(res['subblocks'][1]['merkle_leaves'][0], 'res_2')
        self.assertEqual(res['subblocks'][2]['merkle_leaves'][0], 'res_3')
        self.assertEqual(res['subblocks'][3]['merkle_leaves'][0], 'res_4')

    def test_failed_block_on_one_removes_subblock_from_block(self):
        a = Aggregator(wallet=Wallet(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

        c1 = [MockSBC('input_1', 'res_X', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c2 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_X', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c3 = [MockSBC('input_1', 'res_X', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_i', 'res_X', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c4 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_X', 3).to_dict()]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertTrue(len(res['subblocks']) == 3)

    def test_block_never_received_goes_through_adequate_consensus(self):
        a = Aggregator(
            wallet=Wallet(),
            socket_id=_socket('tcp://127.0.0.1:8888'),
            ctx=zmq.asyncio.Context(),
            driver=BlockchainDriver(),
            seconds_to_timeout=0.5
        )

        c1 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c2 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c3 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_X', 3).to_dict()]

        a.sbc_inbox.q = [c1, c2, c3]

        res = self.loop.run_until_complete(a.gather_subblocks(4, adequate_ratio=0.3))


        self.assertFalse(canonical.block_is_failed(res, '0' * 32, 1))
