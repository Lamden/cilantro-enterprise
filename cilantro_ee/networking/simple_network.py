from cilantro_ee.crypto.wallet import Wallet, verify
import zmq.asyncio
from copy import deepcopy
from cilantro_ee.router import request
import asyncio
from contracting.db.encoder import encode
import time
import hashlib

from cilantro_ee.formatting import rules, primatives

PROOF_EXPIRY = 15
PEPPER = 'cilantroV1'


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


class IdentityProcessor:
    def __init__(self, wallet: Wallet, pepper: str, ip_string: str):
        self.pepper = pepper
        self.wallet = wallet
        self.ip_string = ip_string

    async def process_msg(self, msg):
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


class JoinProcessor:
    def __init__(self, ctx, peers):
        self.ctx = ctx
        self.peers = peers

    async def process_msg(self, msg):
        # Send ping to peer server to verify

        if not primatives.check_format(msg, rules.JOIN_MESSAGE_RULES):
            return

        response = await request(socket_str=msg.get('ip'), service='identity', msg={}, ctx=self.ctx)

        if response is None:
            return

        if not verify_proof(response, PEPPER):
            return

        if response not in self.peers:
            await self.forward_to_peers(response)

        self.peers[msg.get('vk')] = msg.get('ip')

        return {
            'peers': self.peers
        }

    async def forward_to_peers(self, msg):
        for peer in self.peers:
            asyncio.ensure_future(
                request(
                    socket_str=peer,
                    service='join',
                    msg=msg,
                    ctx=self.ctx
                )
            )


class Network:
    def __init__(self, wallet: Wallet, socket_base: str, ctx: zmq.asyncio.Context, pepper: str):
        self.wallet = wallet
        self.socket_base = socket_base
        self.ctx = ctx
        self.pepper = pepper

        self.peers = {}

        self.join_processor = JoinProcessor(ctx=self.ctx, peers=self.peers)

        self.join_msg = {
            'service': 'join',
            'msg': {
                'ip': self.socket_base,
                'vk': self.wallet.verifying_key().hex()
            }
        }

    async def start(self, bootnodes):
        # Join all bootnodes

        to_contact = deepcopy(bootnodes)

        while len(to_contact) > 0:
            coroutines = [
                request(
                    socket_str=node,
                    service='join',
                    msg=self.join_msg,
                    ctx=self.ctx
                ) for node in bootnodes
            ]

            results = await asyncio.gather(*coroutines)

            for result in results:
                if result is None:
                    continue

                if not self.verify_join(result):
                    continue

                self.peers.update(result['peers'])

                results.remove(result)

    def join(self, seednode):
        pass

    def verify_join(self, msg):
        if msg.get('peers') is None:
            return False

        # for peer in peers,
        # check if the contents adhere to JOIN_MESSAGE_RULES
        # also add if not in join

        return True
