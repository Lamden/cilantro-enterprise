from zmq.auth.asyncio import AsyncioAuthenticator
from zmq.error import ZMQBaseError
from zmq.auth.certs import _write_key_file, _cert_public_banner
from zmq.utils import z85
import shutil
import zmq.asyncio
import asyncio
import pathlib
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519
from cilantro_ee.logger.base import get_logger
from contracting.client import ContractingClient

CERT_DIR = 'cilsocks'
DEFAULT_DIR = pathlib.Path.home() / CERT_DIR
DEFAULT_DOMAIN = '*'


class SocketAuthenticator:
    def __init__(self, client: ContractingClient, ctx: zmq.asyncio.Context, bootnodes: dict={},
                 loop=asyncio.get_event_loop(), domain='*', cert_dir=CERT_DIR, debug=True):

        # Create the directory if it doesn't exist
        self.client = client

        self.cert_dir = pathlib.Path.home() / cert_dir
        self.cert_dir.mkdir(parents=True, exist_ok=True)

        self.ctx = ctx

        self.domain = domain

        self.loop = loop

        self.log = get_logger('zmq.auth')
        self.log.propagate = debug

        # This should throw an exception if the socket already exist
        try:
            self.authenticator = AsyncioAuthenticator(context=self.ctx, loop=self.loop)
            self.authenticator.start()

            # Add bootnodes
            for node in bootnodes.keys():
                self.add_verifying_key(node)

            self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)
        except ZMQBaseError:
            pass
            #raise Exception('AsyncioAuthenicator could not be started. Is it already running?')

    def refresh_governance_sockets(self):
        masternode_list = self.client.get_var(
            contract='masternodes',
            variable='S',
            arguments=['members']
        )

        delegate_list = self.client.get_var(
            contract='delegates',
            variable='S',
            arguments=['members']
        )

        on_deck_masternode = self.client.get_var(
            contract='elect_masternodes',
            variable='top_candidate'
        )

        on_deck_delegate = self.client.get_var(
            contract='elect_delegates',
            variable='top_candidate'
        )

        self.flush_all_keys()

        for mn in masternode_list:
            self.add_verifying_key(mn)

        for dl in delegate_list:
            self.add_verifying_key(dl)

        if on_deck_masternode is not None:
            self.add_verifying_key(on_deck_masternode)

        if on_deck_delegate is not None:
            self.add_verifying_key(on_deck_delegate)

        self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)

    def add_verifying_key(self, vk: str):
        # Convert to bytes if hex string
        bvk = bytes.fromhex(vk)

        try:
            pk = crypto_sign_ed25519_pk_to_curve25519(bvk)
        # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
        except RuntimeError:
            return

        zvk = z85.encode(pk).decode('utf-8')
        _write_key_file(self.cert_dir / f'{vk}.key', banner=_cert_public_banner, public_key=zvk)

    def flush_all_keys(self):
        shutil.rmtree(str(self.cert_dir))
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    def configure(self):
        self.authenticator.configure_curve(domain=self.domain, location=self.cert_dir)


def add_verifying_key(vk: str, cert_dir: pathlib.Path=DEFAULT_DIR):
    bvk = bytes.fromhex(vk)

    try:
        pk = crypto_sign_ed25519_pk_to_curve25519(bvk)
    # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
    except RuntimeError:
        return

    zvk = z85.encode(pk).decode('utf-8')
    _write_key_file(cert_dir / f'{vk}.key', banner=_cert_public_banner, public_key=zvk)


def flush_all_keys(cert_dir: pathlib.Path=DEFAULT_DIR):
    shutil.rmtree(str(cert_dir))
    cert_dir.mkdir(parents=True, exist_ok=True)


def refresh_governance_sockets(client: ContractingClient, cert_dir: pathlib.Path):
    masternode_list = client.get_var(
        contract='masternodes',
        variable='S',
        arguments=['members']
    )

    delegate_list = client.get_var(
        contract='delegates',
        variable='S',
        arguments=['members']
    )

    on_deck_masternode = client.get_var(
        contract='elect_masternodes',
        variable='top_candidate'
    )

    on_deck_delegate = client.get_var(
        contract='elect_delegates',
        variable='top_candidate'
    )

    flush_all_keys(cert_dir)

    for mn in masternode_list:
        add_verifying_key(mn, cert_dir)

    for dl in delegate_list:
        add_verifying_key(dl, cert_dir)

    if on_deck_masternode is not None:
        add_verifying_key(on_deck_masternode, cert_dir)

    if on_deck_delegate is not None:
        add_verifying_key(on_deck_delegate, cert_dir)
