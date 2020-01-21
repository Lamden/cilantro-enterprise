import os
from contracting.db.encoder import encode, decode
from cilantro_ee.crypto.wallet import Wallet
import asyncio
from copy import deepcopy

from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.nodes.masternode.masternode import Masternode

from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.crypto.transaction import TransactionBuilder
from contracting import config

from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import capnp

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

import aiohttp


def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass


class MockDB:
    def __init__(self):
        self.d = {}

    def exists(self, key):
        return not self.d.get(key) is None

    def get(self, key):
        val = self.d.get(key)
        return decode(val)

    def set(self, key, value):
        v = encode(value)
        self.d[key] = v

    def iter(self, prefix):
        return [k for k in self.d.keys() if k.startswith(prefix)]


class IsolatedDriver(BlockchainDriver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = MockDB()

    def get(self, key):
        return self.db.get(key)

    def set(self, key, value):
        self.db.set(key, value)

    def commit(self):
        pass


def make_network(masternodes, delegates, ctx):
    mn_wallets = [Wallet() for _ in range(masternodes)]
    dl_wallets = [Wallet() for _ in range(delegates)]

    constitution = {
        'masternodes': [mn.verifying_key().hex() for mn in mn_wallets],
        'delegates': [dl.verifying_key().hex() for dl in dl_wallets],
        'witnesses': [],
        'schedulers': [],
        'notifiers': [],
        'enable_stamps': False,
        'enable_nonces': False,
        'masternode_min_quorum': 2,
        'delegate_min_quorum': 2,
        'witness_min_quorum': 0,
        'notifier_min_quorum': 0,
        'scheduler_min_quorum': 0
    }

    mns = []
    dls = []
    bootnodes = None
    node_count = 0
    for wallet in mn_wallets:
        driver = IsolatedDriver()
        ipc = f'/tmp/n{node_count}'
        make_ipc(ipc)

        if bootnodes is None:
            bootnodes = [f'ipc://{ipc}']

        mn = Masternode(
            wallet=wallet,
            ctx=ctx,
            socket_base=f'ipc://{ipc}',
            bootnodes=bootnodes,
            constitution=deepcopy(constitution),
            webserver_port=18080 + node_count,
            driver=driver
        )

        mns.append(mn)
        node_count += 1

    for wallet in dl_wallets:
        driver = IsolatedDriver()
        ipc = f'/tmp/n{node_count}'
        make_ipc(ipc)

        dl = Delegate(
            wallet=wallet,
            ctx=ctx,
            socket_base=f'ipc://{ipc}',
            constitution=deepcopy(constitution),
            bootnodes=bootnodes,
            driver=driver
        )

        dls.append(dl)
        node_count += 1

    return mns, dls


def make_start_awaitable(mns, dls):
    coros = []
    for mn in mns:
        coros.append(mn.start())

    for dl in dls:
        coros.append(dl.start())

    return asyncio.gather(*coros)


def make_tx_packed(processor, contract_name, function_name, sender=Wallet(), kwargs={}, drivers=[]):
    batch = TransactionBuilder(
        sender=sender.verifying_key(),
        contract=contract_name,
        function=function_name,
        kwargs=kwargs,
        stamps=10000,
        processor=processor,
        nonce=0
    )

    batch.sign(sender.signing_key())
    b = batch.serialize()

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       sender.verifying_key().hex())

    for driver in drivers:
        driver.set(balances_key, 1_000_000)
        driver.commit()

    return b


async def send_tx(masternode: Masternode, nodes, contract, function, sender=Wallet(), kwargs={}, sleep=2):
    async with aiohttp.ClientSession() as session:
        r = await session.post(
            url=f'http://127.0.0.1:{masternode.webserver.port}/',
            data=make_tx_packed(
                masternode.wallet.verifying_key(),
                contract_name=contract,
                function_name=function,
                sender=sender,
                kwargs=kwargs,
                drivers=[node.driver for node in nodes]
            )
        )

    res = await r.json()
    await asyncio.sleep(sleep)
    return res

# async def
# async with aiohttp.ClientSession() as session:
#     r = await session.post('http://127.0.0.1:8081/',
#                  data=make_tx_packed(mnw2.verifying_key(), 'testing', 'test', drivers=[md1, md2, dd1, dd2]))
#
# res = await
# r.json()
