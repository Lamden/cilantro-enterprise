from cilantro_ee.constants import conf
from cilantro_ee.constants.ports import DHT_PORT, DISCOVERY_PORT, EVENT_PORT
from cilantro_ee.constants.overlay_network import PEPPER
from cilantro_ee.protocol.overlay.kademlia import discovery
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet

from cilantro_ee.storage.vkbook import PhoneBook

from functools import partial
import asyncio
import json
import zmq
from cilantro_ee.logger.base import get_logger

log = get_logger('NetworkService')


def ip_string_from_bytes(b: bytes):
    b = bytearray(b)
    ip = [str(byte) for byte in b[0:4]]
    ip = '.'.join(ip)
    return ip


def bytes_from_ip_string(ip: str):
    b = ip.split('.')
    bb = [int(i) for i in b]
    return bytes(bb)


def strip_protocol_and_port(zmq_str):
    stripped = zmq_str.split('//')[1]
    stripped = stripped.split(':')[0]
    return stripped


class KTable:
    def __init__(self, data: dict, initial_peers={}, response_size=10):
        self.data = data
        self.peers = initial_peers
        self.response_size = response_size

    @staticmethod
    def distance(string_a, string_b):
        int_val_a = int(string_a.encode().hex(), 16)
        int_val_b = int(string_b.encode().hex(), 16)
        return int_val_a ^ int_val_b

    def find(self, key):
        if key in self.data:
            return self.data
        elif key in self.peers:
            return {
                key: self.peers[key]
            }
        else:
            # Do an XOR sort on all the keys to find neighbors
            sort_func = partial(self.distance, string_b=key)
            closest_peer_keys = sorted(self.peers.keys(), key=sort_func)

            # Only keep the response size number
            closest_peer_keys = closest_peer_keys[:self.response_size]

            # Dict comprehension
            neighbors = {k: self.peers[k] for k in closest_peer_keys}

            return neighbors


class PeerServer(services.RequestReplyService):
    def __init__(self, address: str, event_publisher_address: str, table: KTable, wallet: Wallet, ctx=zmq.Context,
                 linger=2000, poll_timeout=500):

        super().__init__(address=address,
                         wallet=wallet,
                         ctx=ctx,
                         linger=linger,
                         poll_timeout=poll_timeout)

        self.table = table

        self.event_service = services.SubscriptionService(ctx=self.ctx)
        self.event_publisher = self.ctx.socket(zmq.PUB)
        self.event_publisher.bind(event_publisher_address)

        self.event_queue_loop_running = False

    def handle_msg(self, msg):
        msg = msg.decode()
        command, args = json.loads(msg)

        if command == 'find':
            response = self.table.find(args)
            response = json.dumps(response).encode()
            return response
        if command == 'join':
            vk, ip = args # unpack args
            asyncio.ensure_future(self.handle_join(vk, ip))
            return None

    async def handle_join(self, vk, ip):
        result = self.table.find(vk)

        if vk not in result or result[vk] != ip:
            # Ping discovery server
            _, responded_vk = await discovery.ping(ip, pepper=PEPPER.encode(), ctx=self.ctx, timeout=1000)

            if responded_vk.hex() == vk:
                # Valid response
                self.table.peers[vk] = ip

                # Publish a message that a new node has joined
                msg = {'join': (vk, ip)}
                jmsg = json.dumps(msg)
                await self.event_publisher.send(jmsg)

    async def process_event_subscription_queue(self):
        self.event_queue_loop_running = True

        while self.event_queue_loop_running:
            if len(self.event_service.received) > 0:
                message, sender = self.event_service.received.pop(0)
                command, args = message
                vk, ip = args

                if command == 'join':
                    asyncio.ensure_future(self.handle_join(vk=vk, ip=ip))

                elif command == 'leave':
                    # Ping to make sure the node is actually offline
                    _, responded_vk = await discovery.ping(ip, pepper=PEPPER.encode(),
                                                           ctx=self.ctx, timeout=1000)

                    # If so, remove it from our table
                    if responded_vk is None:
                        del self.table[vk]

    def start(self):
        tasks = asyncio.gather(
            self.serve(),
            self.event_service.serve(),
            self.process_event_subscription_queue()
        )
        asyncio.ensure_future(tasks)

class Network:
    def __init__(self, wallet, peer_service_port: int,
                 ctx=zmq.asyncio.Context(), ip=conf.HOST_IP,
                 bootnodes=conf.BOOT_DELEGATE_IP_LIST + conf.BOOT_MASTERNODE_IP_LIST):

        self.wallet = wallet
        self.ctx = ctx

        self.bootnodes = bootnodes

        data = {
            self.wallet.verifying_key().hex(): bytes_from_ip_string(conf.HOST_IP)
        }
        self.table = KTable(data=data)

        peer_service_address = 'tcp://{}:{}'.format(ip, peer_service_port)
        self.peer_service = PeerServer(address=peer_service_address, table=self.table,
                                       wallet=self.wallet, ctx=self.ctx)

    async def discover_bootnodes(self):
        responses = await discovery.discover_nodes(self.bootnodes, pepper=PEPPER.encode(),
                                                   ctx=self.ctx, timeout=100)

        for ip, vk in responses.items():
            self.table.peers[vk] = ip  # Should be stripped of port and tcp

        # Crawl bootnodes 'announcing' yourself

    async def wait_for_quorum(self):
        # Determine how many more nodes we need to find
        masternodes_left = PhoneBook.masternode_quorum_min
        delegates_left = PhoneBook.delegate_quorum_min

        # Storing these in local vars saves DB hits
        current_masternodes = PhoneBook.masternodes
        current_delegates = PhoneBook.delegates

        current_peers = {}
        current_peers.update(self.table.peers)
        current_peers.update(self.table.data)

