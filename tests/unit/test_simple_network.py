from unittest import TestCase
from cilantro_ee.networking.simple_network import *
from cilantro_ee.crypto.wallet import Wallet

import asyncio
import zmq.asyncio


class TestProcessors(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_identity_processor_create_proof(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1'
        )

        proof = i.create_proof()

        self.assertTrue(verify_proof(proof, 'test'))

    def test_identity_false_proof_fails(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1'
        )

        proof = i.create_proof()

        proof['signature'] = '0' * 128

        self.assertFalse(verify_proof(proof, 'test'))

    def test_proof_timeout_fails(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1'
        )

        proof = i.create_proof()

        proof['timestamp'] = 0

        self.assertFalse(verify_proof(proof, 'test'))

    def test_process_msg_returns_proof_no_matter_what(self):
        w = Wallet()
        i = IdentityProcessor(
            wallet=w,
            pepper='test',
            ip_string='tcp://127.0.0.1'
        )

        loop = asyncio.get_event_loop()
        proof = loop.run_until_complete(i.process_msg({}))

        self.assertTrue(verify_proof(proof, 'test'))

    def test_join_processor_returns_none_if_message_not_formatted(self):
        msg = {
            'vk': 'bad',
            'ip': 'bad'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers={}
        )

        res = self.loop.run_until_complete(j.process_msg(msg))

        self.assertIsNone(res)

    def test_join_processor_good_message_offline_returns_none(self):
        msg = {
            'vk': '0' * 64,
            'ip': 'tcp://127.0.0.1'
        }

        j = JoinProcessor(
            ctx=self.ctx,
            peers={}
        )

        res = self.loop.run_until_complete(j.process_msg(msg))
        self.assertIsNone(res)

