from cilantro_ee.crypto import transaction
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto import canonical
from contracting.db.driver import decode
from contracting.client import ContractingClient
from cilantro_ee.nodes.delegate import execution
from cilantro_ee import storage
import zmq.asyncio
import asyncio

import time
from datetime import datetime

from unittest import TestCase


def generate_blocks(number_of_blocks, subblocks=[]):
    previous_hash = '0' * 64
    previous_number = 0

    blocks = []
    for i in range(number_of_blocks):
        if len(subblocks) > i:
            subblock = subblocks[i]
        else:
            subblock = []

        new_block = canonical.block_from_subblocks(
            subblocks=subblock,
            previous_hash=previous_hash,
            block_num=previous_number + 1
        )

        blocks.append(new_block)

        previous_hash = new_block['hash']
        previous_number += 1

    return blocks


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestDelegate(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        self.client = ContractingClient()
        self.client.flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.client.flush()
        self.ctx.destroy()
        self.loop.close()

    def test_execute_tx_returns_successful_output(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
                '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'jeff'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        result = execution.execute_tx(self.client.executor, decode(tx), stamp_cost=20_000)

        self.assertEqual(result['status'], 0)
        self.assertEqual(result['state'][0]['key'], 'testing.v')
        self.assertEqual(result['state'][0]['value'],  'jeff')
        self.assertEqual(result['stamps_used'], 1000)

    def test_generate_environment_creates_datetime_wrapped_object(self):
        timestamp = time.time()

        e = execution.generate_environment(self.client.raw_driver, timestamp, 'A' * 64)

        t = datetime.utcfromtimestamp(timestamp)

        #self.assertEqual(type(e['now']), Datetime)
        self.assertEqual(e['now'].year, t.year)
        self.assertEqual(e['now'].month, t.month)
        self.assertEqual(e['now'].day, t.day)
        self.assertEqual(e['now'].hour, t.hour)
        self.assertEqual(e['now'].minute, t.minute)
        self.assertEqual(e['now'].second, t.second)

    def test_generate_environment_creates_input_hash(self):
        timestamp = time.time()

        e = execution.generate_environment(self.client.raw_driver, timestamp, 'A' * 64)

        self.assertEqual(e['__input_hash'], 'A' * 64)

    def test_generate_environment_creates_block_hash(self):
        timestamp = time.time()

        e = execution.generate_environment(self.client.raw_driver, timestamp, 'A' * 64)

        self.assertEqual(e['block_hash'], storage.get_latest_block_hash(self.client.raw_driver))

    def test_generate_environment_creates_block_num(self):
        timestamp = time.time()

        e = execution.generate_environment(self.client.raw_driver, timestamp, 'A' * 64)

        self.assertEqual(e['block_num'], storage.get_latest_block_height(self.client.raw_driver) + 1)

    def test_execute_tx_batch_returns_all_transactions(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'howdy'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx = decode(tx)

        tx2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2 = decode(tx2)

        tx_batch = {
            'transactions': [tx, tx2]
        }

        results = execution.execute_tx_batch(
            executor=self.client.executor,
            driver=self.client.raw_driver,
            batch=tx_batch,
            timestamp=time.time(),
            input_hash='A' * 64,
            stamp_cost=20_000
        )

        td1, td2 = results

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], 'howdy')
        self.assertEqual(td1['stamps_used'], 1000)

        self.assertEqual(td2['status'], 0)
        self.assertEqual(len(td2['state']), 0)
        self.assertEqual(td2['stamps_used'], 1000)

    def test_execute_work_multiple_transaction_batches_works(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx1_1 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'howdy'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx1_1 = decode(tx1_1)

        tx1_2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx1_2 = decode(tx1_2)

        tx_batch_1 = {
            'transactions': [tx1_1, tx1_2],
            'timestamp': time.time(),
            'input_hash': 'C' * 64
        }

        tx2_1 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': '123'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_1 = decode(tx2_1)

        jeff = Wallet()
        tx2_2 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='set',
            kwargs={'var': 'poo'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_2 = decode(tx2_2)

        tx_batch_2 = {
            'transactions': [tx2_1, tx2_2],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        work = [
            (tx_batch_1['timestamp'], tx_batch_1),
            (tx_batch_2['timestamp'], tx_batch_2)
        ]

        results = execution.execute_work(
            executor=self.client.executor,
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=Wallet(),
            stamp_cost=20_000
        )

        sb1, sb2 = results

        td1, td2 = sb1['transactions']
        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], 'howdy')
        self.assertEqual(td1['stamps_used'], 1000)

        self.assertEqual(td2['status'], 0)
        self.assertEqual(len(td2['state']), 0)
        self.assertEqual(td2['stamps_used'], 1000)

        self.assertEqual(sb1['input_hash'], tx_batch_1['input_hash'])
        self.assertEqual(sb1['subblock'], 0)
        self.assertEqual(sb1['previous'], 'B' * 64)

        td1, td2 = sb2['transactions']
        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], '123')
        self.assertEqual(td1['stamps_used'], 1000)

        self.assertEqual(td2['status'], 0)
        self.assertEqual(td2['state'][0]['key'], 'testing.v')
        self.assertEqual(td2['state'][0]['value'], 'poo')
        self.assertEqual(td2['stamps_used'], 1000)

        self.assertEqual(sb2['input_hash'], tx_batch_2['input_hash'])
        self.assertEqual(sb2['subblock'], 1)
        self.assertEqual(sb2['previous'], 'B' * 64)
