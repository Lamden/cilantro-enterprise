from cilantro_ee.crypto.wallet import Wallet
import zmq.asyncio
from copy import deepcopy
from cilantro_ee import struct, services
import asyncio


class IdentityProcessor:
    def __init__(self, wallet: Wallet, pepper: str):
        self.response = wallet.sign(pepper)

    async def process_msg(self, msg):
        return self.response


EXAMPLE_MESSAGE = {
    'ip': '127.0.0.1',
    'vk': 'asdfasdfasdf'
}


class JoinProcessor:
    def __init__(self, ctx, peers):
        self.ctx = ctx
        self.peers = peers

    async def process_msg(self, msg):
        # Send ping to peer server to verify

        if msg.get('ip') is None:
            return

        if msg.get('vk') is None:
            return

        socket = struct._socket(msg.get('ip'))

        request = {
            'service': 'identity',
            'msg': {
            }
        }

        response = await services.get(socket_id=socket, msg=request, ctx=self.ctx, timeout=1000)

        if response is None:
            return

        if not self.verify_ping(response):
            return

        if response not in self.peers:
            await self.forward_to_peers(response)

        self.peers[msg.get('vk')] = msg.get('ip')

        return {
            'response': 'accepted'
        }

    def verify_ping(self, ping):
        pass

    async def forward_to_peers(self, msg):
        pass


class PeerProcessor:
    def __init__(self):
        self.masternodes = {}
        self.delegates = {}

    async def process_msg(self, msg):
        pass


class Network:
    def __init__(self, wallet: Wallet, socket_base: str, ctx: zmq.asyncio.Context, pepper: str):
        self.wallet = wallet
        self.socket_base = socket_base
        self.ctx = ctx
        self.pepper = pepper

        self.peers = {}

        self.join_processor = JoinProcessor(ctx=self.ctx, peers=self.peers)

        self.join_msg = {
            'service': 'identity',
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
                services.get(socket_id=node, msg=self.join_msg, ctx=self.ctx, timeout=1000) for node in bootnodes
            ]

            results = await asyncio.gather(*coroutines)

            for result in results:
                if result is None:
                    continue

                if not self.verify_join(result):
                    continue

                self.add_peer(result)
                results.remove(result)


        pass

    def add_peer(self, result):
        pass

    def join(self, seednode):
        pass

    def verify_join(self, msg):
        if msg.get('response') is None:
            return False

        if msg.get('response') != 'accepted':
            return False

        return True
