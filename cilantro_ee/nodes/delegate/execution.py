from contracting.execution.executor import Executor
from contracting.stdlib.bridge.time import Datetime
from contracting.db.encoder import encode, decode, safe_repr
from cilantro_ee.crypto.canonical import tx_hash_from_tx, format_dictionary, merklize
from cilantro_ee.logger.base import get_logger
from datetime import datetime
import heapq
from cilantro_ee import storage

log = get_logger('EXE')

import multiprocessing as mp
from time import time
__N_WORKER__ = 3
PoolExecutor = None
def setPoolExecutor(executor):
    global PoolExecutor
    PoolExecutor = executor


def execute_tx(transaction, stamp_cost, environment: dict={}):
    executor = PoolExecutor
    output = executor.execute(
        sender=transaction['payload']['sender'],
        contract_name=transaction['payload']['contract'],
        function_name=transaction['payload']['function'],
        stamps=transaction['payload']['stamps_supplied'],
        stamp_cost=stamp_cost,
        kwargs=transaction['payload']['kwargs'],
        environment=environment,
        auto_commit=False
    )
    log.debug(output)

    tx_hash = tx_hash_from_tx(transaction)

    writes = [{'key': k, 'value': v} for k, v in output['writes'].items()]

    tx_output = {
        'hash': tx_hash,
        'transaction': transaction,
        'status': output['status_code'],
        'state': writes,
        'stamps_used': output['stamps_used'],
        'result': safe_repr(output['result'])
    }
    tx_output = format_dictionary(tx_output)
    executor.driver.pending_writes.clear() # add
    return tx_output


def generate_environment(driver, timestamp, input_hash):
    now = Datetime._from_datetime(
        datetime.utcfromtimestamp(timestamp)
    )

    return {
        'block_hash': storage.get_latest_block_hash(driver),
        'block_num': storage.get_latest_block_height(driver) + 1,
        '__input_hash': input_hash,  # Used for deterministic entropy for random games
        'now': now
    }

result_list2 = []
def tx_result(result):
    result_list2.append(result)

def execute_tx_batch(executor, driver, batch, timestamp, input_hash, stamp_cost):
    environment = generate_environment(driver, timestamp, input_hash)
    # Each TX Batch is basically a subblock from this point of view and probably for the near future

    pool = mp.Pool(processes=__N_WORKER__)
    setPoolExecutor(executor)
    i= 1
    s = time()
    global result_list2
    result_list2 = []
    log.debug(f"Start Pool  ")

    for transaction in batch['transactions']:
        log.debug(f'Transaction {i}   {type(executor)}')  # {execute_tx(transaction, stamp_cost, environment)}
        i += 1
        pool.apply_async(execute_tx, args = (transaction, stamp_cost, environment, ) , callback = tx_result)

    pool.close()
    pool.join()
    log.debug(f"End of pool. result_list={result_list2} duration= {time() - s}")
    tx_data = result_list2
    log.debug(f"tx_data={len(tx_data)}")

    return tx_data

# def execute_tx_batch(executor, driver, batch, timestamp, input_hash, stamp_cost):
#     environment = generate_environment(driver, timestamp, input_hash)
#
#     # Each TX Batch is basically a subblock from this point of view and probably for the near future
#     tx_data = []
#     for transaction in batch['transactions']:
#         tx_data.append(execute_tx(executor=executor,
#                                   transaction=transaction,
#                                   environment=environment,
#                                   stamp_cost=stamp_cost)
#                        )
#
#     return tx_data


def execute_work(executor, driver, work, wallet, previous_block_hash, stamp_cost, parallelism=4):
    # Assume single threaded, single process for now.
    subblocks = []
    i = 0

    for tx_batch in work:
        results = execute_tx_batch(
            executor=executor,
            driver=driver,
            batch=tx_batch,
            timestamp=tx_batch['timestamp'],
            input_hash=tx_batch['input_hash'],
            stamp_cost=stamp_cost
        )

        if len(results) > 0:
            merkle = merklize([encode(r).encode() for r in results])
            proof = wallet.sign(merkle[0])
        else:
            merkle = merklize([bytes.fromhex(tx_batch['input_hash'])])
            proof = wallet.sign(tx_batch['input_hash'])

        merkle_tree = {
            'leaves': merkle,
            'signature': proof
        }

        sbc = {
            'input_hash': tx_batch['input_hash'],
            'transactions': results,
            'merkle_tree': merkle_tree,
            'signer': wallet.verifying_key,
            'subblock': i % parallelism,
            'previous': previous_block_hash
        }

        sbc = format_dictionary(sbc)

        subblocks.append(sbc)
        i += 1

    return subblocks
