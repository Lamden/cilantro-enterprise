import time
import hashlib
import asyncio
import zmq.asyncio
from zmq.error import ZMQBaseError
from zmq.utils import z85
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519
from contracting.db.encoder import encode

from cilantro_ee.formatting import rules, primatives
from cilantro_ee.crypto.wallet import Wallet, verify
from cilantro_ee import router
from cilantro_ee.logger.base import get_logger

PROOF_EXPIRY = 15
PEPPER = 'cilantroV1'
LOGGER = get_logger('Network')

JOIN_SERVICE = 'join'           # Unsecured
IDENTITY_SERVICE = 'identity'   # Unsecured


def verify_proof(proof, pepper):
    # Proofs expire after a minute
    if not primatives.check_format(proof, rules.PROOF_MESSAGE_RULES):
        return False

    if int(time.time()) - proof['timestamp'] > PROOF_EXPIRY:
        return False

    message = [pepper, proof['ip'], proof['timestamp']]
    message_bytes = encode(message).encode()

    h = hashlib.sha3_256()
    h.update(message_bytes)

    return verify(proof['vk'], h.digest().hex(), proof['signature'])


class IdentityProcessor(router.Processor):
    def __init__(self, wallet: Wallet, ip_string: str, pepper: str=PEPPER):
        self.pepper = pepper
        self.wallet = wallet
        self.ip_string = ip_string

    async def process_message(self, msg):
        return self.create_proof()

    def create_proof(self):
        now = int(time.time())
        message = [self.pepper, self.ip_string, now]

        message_bytes = encode(message).encode()

        h = hashlib.sha3_256()
        h.update(message_bytes)

        signature = self.wallet.sign(h.digest())

        proof = {
            'signature': signature.hex(),
            'vk': self.wallet.verifying_key().hex(),
            'timestamp': now,
            'ip': self.ip_string
        }

        return proof


class JoinProcessor(router.Processor):
    def __init__(self, ctx, peers, wallet):
        self.ctx = ctx
        self.peers = peers
        self.wallet = wallet

    async def process_message(self, msg):
        # Send ping to peer server to verify
        if not primatives.check_format(msg, rules.JOIN_MESSAGE_RULES):
            return

        response = await router.request(msg={}, service=IDENTITY_SERVICE, wallet=self.wallet, vk=msg.get('vk'),
                                        ip=msg.get('ip'), ctx=self.ctx)

        if response is None:
            return

        if not verify_proof(response, PEPPER):
            return

        if msg.get('vk') not in self.peers:
            await router.secure_multicast(msg=msg, service=JOIN_SERVICE, peer_map=self.peers, ctx=self.ctx, wallet=self.wallet)

        self.peers[msg.get('vk')] = msg.get('ip')

        return {
            'peers': [{'vk': v, 'ip': i} for v, i in self.peers.items()]
        }

# Bootnodes:
# {
#    ip: vk
# }

class Network:
    def __init__(self, wallet: Wallet, ip_string: str, ctx: zmq.asyncio.Context, router: router.Router, pepper: str=PEPPER):
        self.wallet = wallet
        self.ctx = ctx

        self.peers = dict()

        # Add processors to router to accept and process networking messages
        self.ip = ip_string
        self.vk = self.wallet.verifying_key().hex()
        self.join_processor = JoinProcessor(ctx=self.ctx, peers=self.peers, wallet=self.wallet)
        self.identity_processor = IdentityProcessor(wallet=self.wallet, ip_string=ip_string, pepper=pepper)

        self.router = router
        self.router.add_service(JOIN_SERVICE, self.join_processor)
        self.router.add_service(IDENTITY_SERVICE, self.identity_processor)

        self.join_msg = {
            'ip': ip_string,
            'vk': self.wallet.verifying_key().hex()
        }

    async def start(self, bootnodes: dict, vks: list):
        # This can be made less redundant by building a do while loop
        # Connect to all bootnodes
        connected_bootnodes = {}
        for vk, ip in bootnodes.items():
            socket = self.build_socket(ip, vk)
            if socket is None:
                continue
            connected_bootnodes[vk] = socket

        # Then ping them all
        while not self.all_vks_found(vks):

            coroutines = [router.request(
                msg=self.join_msg, service=JOIN_SERVICE, socket=ip) for vk, ip, in connected_bootnodes.items()]

            results = await asyncio.gather(*coroutines)

            for result in results:
                if result is None or result == {'response': 'ok'}:
                    continue

                for peer in result['peers']:
                    if self.peers.get(peer['vk']) is not None:
                        continue

                    socket = self.build_socket(peer['ip'], peer['vk'])

                    if socket is None:
                        continue

                    self.peers[peer['vk']] = socket

        # Disconnect from the connected bootnodes
        for vk, ip in connected_bootnodes.items():
            ip.close()

    def build_socket(self, ip, peer_vk):
        socket = self.ctx.socket(zmq.DEALER)

        if self.router.secure:
            socket.curve_secretkey = self.wallet.curve_sk
            socket.curve_publickey = self.wallet.curve_vk

            try:
                pk = crypto_sign_ed25519_pk_to_curve25519(bytes.fromhex(peer_vk))
            # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
            except RuntimeError:
                return None

            zvk = z85.encode(pk)

            socket.curve_serverkey = zvk

        try:
            socket.connect(ip)
        except ZMQBaseError:
            return None

        return socket

    def all_vks_found(self, vks):
        for vk in vks:
            if self.peers.get(vk) is None:
                return False
        return True
