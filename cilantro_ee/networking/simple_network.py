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

        if msg.get('vk') not in self.peers:
            await self.forward_to_peers(msg)

        self.peers[msg.get('vk')] = msg.get('ip')

        return {
            'peers': [{'vk': v, 'ip': i} for v, i in self.peers.items()]
        }

    async def forward_to_peers(self, msg):
        for peer in self.peers.values():
            asyncio.ensure_future(
                request(
                    socket_str=peer,
                    service='join',
                    msg=msg,
                    ctx=self.ctx
                )
            )


class Network:
    def __init__(self, wallet: Wallet, ip_string: str, ctx: zmq.asyncio.Context, pepper: str=PEPPER):
        self.wallet = wallet
        self.ctx = ctx
        self.pepper = pepper

        self.peers = {
            self.wallet.verifying_key().hex(): ip_string
        }

        self.join_processor = JoinProcessor(ctx=self.ctx, peers=self.peers)

        self.join_msg = {
            'service': 'join',
            'msg': {
                'ip': ip_string,
                'vk': self.wallet.verifying_key().hex()
            }
        }

    async def start(self, bootnodes, vks):
        # Join all bootnodes
        while not self.all_vks_found(vks):
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

                for peer in result['peers']:
                    self.peers.update(
                        {
                            peer['vk']: peer['ip']
                        }
                    )

    def all_vks_found(self, vks):
        for vk in vks:
            if self.peers.get(vk) is None:
                return False
        return True