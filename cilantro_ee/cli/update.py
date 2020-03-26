import aiohttp
import asyncio
import requests
import subprocess
import os
from getpass import getpass
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder
from cilantro_ee.cli.utils import get_update_state
from cilantro_ee.cli.start import resolve_constitution
from cilantro_ee.logger.base import get_logger
log = get_logger('Cmd-upd')


async def cil_interface(server, packed_data, sleep=2):
    async with aiohttp.ClientSession() as session:
        r = await session.post(
            url=f'http://{server}:18080/',
            data=packed_data
        )
        result = await r.json()
        await asyncio.sleep(sleep)
        return result


def verify_access():
    while True:
        sk = getpass('Signing Key in Hex Format: ')

        try:
            wallet = Wallet(seed=bytes.fromhex(sk))
            print('Access validated')
            return wallet
        except:
            print('Invalid format! Try again.')


def trigger(pkg=None, iaddr=None):

    my_wallet = verify_access()
    pepper = pkg  #TODO replace with verified pepper pkg
    kwargs = {'pepper': pepper, 'initiator_vk': my_wallet.verifying_key().hex()}
    vk = my_wallet.verifying_key()

    SERVER = f'http://{iaddr}:18080'

    nonce_req = requests.get('{}/nonce/{}'.format(SERVER, my_wallet.verifying_key().hex()))
    nonce = nonce_req.json()['nonce']

    #TODO bail out if vk is not in list of master nodes

    pack = TransactionBuilder(
        sender=vk,
        contract='upgrade',
        function='trigger_upgrade',
        kwargs=kwargs,
        stamps=100_000,
        processor=vk,
        nonce=nonce
    )

    pack.sign(my_wallet.signing_key())
    m = pack.serialize()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(cil_interface(server=iaddr, packed_data=m, sleep=2))


def vote(iaddr):
    my_wallet = verify_access()

    file = input("Enter patch to constitution:")

    constitution = resolve_constitution(fp=file)

    # TODO randomize proc in future
    proc = constitution.get("masternodes", "")

    SERVER = f'http://{iaddr}:18080'

    nonce_req = requests.get('{}/nonce/{}'.format(SERVER, my_wallet.verifying_key().hex()))
    nonce = nonce_req.json()['nonce']
    vk = my_wallet.verifying_key()

    kwargs = {'vk': my_wallet.verifying_key().hex()}

    pack = TransactionBuilder(
        sender=my_wallet.verifying_key(),
        contract='upgrade',
        function='vote',
        kwargs=kwargs,
        stamps=100_000,
        processor=bytes.fromhex(proc[0]),
        nonce=nonce
    )

    pack.sign(my_wallet.signing_key())
    m = pack.serialize()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(cil_interface(server=iaddr, packed_data=m, sleep=2))


def check_ready_quorum(iaddr):
    get_update_state()


def run(*args):
    return subprocess.check_call(['git'] + list(args))


def upgrade():
    try:
        base_dir = input("Absolute path package directory:")
        os.chdir(base_dir)

        # get latest release
        rel = input("Enter New Release branch:")
        br = f'{rel}'

        run("fetch")
        run("checkout", "-b", br)
    except OSError as err:
        log.error("OS error: {0}".format(err))
        return
    except:
        log.error("Unexpected error:", sys.exc_info())
        return

    # rebuilding package
    os.chdir(base_dir)
    subprocess.run('python3 setup.py develop', shell=True)
