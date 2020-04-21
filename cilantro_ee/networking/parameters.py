import cilantro_ee.sockets.struct
from cilantro_ee.sockets.services import get

import json
import zmq.asyncio
import asyncio

from cilantro_ee.logger.base import get_logger
from os import getenv as env


PEPPER = env('PEPPER', 'cilantro_pepper')
DISCOVERY_PORT = 19000
AUTH_PORT = 19001
DHT_PORT = 19002
EVENT_PORT = 19003
BLOCK_SERVER = 19004
MN_PUB_PORT = 19005
DELEGATE_PUB_PORT = 19006
TX_BATCH_INFORMER_PORT = 19007
BLOCK_NOTIF_PORT = 19008
TX_BATCHER_PORT = 19009
BLOCK_AGG_CONTROLLER_PORT = 19010
INCOMING_WORK_PORT = 19011


class ServiceType:
    PEER = 0
    EVENT = 1
    DISCOVERY = 2
    BLOCK_SERVER = 3
    SUBBLOCK_BUILDER_PUBLISHER = 4
    BLOCK_AGGREGATOR = 5
    TX_BATCH_INFORMER = 6
    BLOCK_NOTIFICATIONS = 7
    TX_BATCHER = 8
    BLOCK_AGGREGATOR_CONTROLLER = 9
    INCOMING_WORK = 10


class NetworkParameters:
    def __init__(self,
                 peer_port=DHT_PORT, peer_ipc='peers',
                 event_port=EVENT_PORT, event_ipc='events',
                 discovery_port=DISCOVERY_PORT, discovery_ipc='discovery',
                 block_port=BLOCK_SERVER, block_ipc='blocks',
                 sbb_pub_port=MN_PUB_PORT, sbb_pub_ipc='sbb_publisher',
                 block_agg_port=DELEGATE_PUB_PORT, block_agg_ipc='block_aggregator',
                 tx_batch_informer_port=TX_BATCH_INFORMER_PORT, tx_batch_informer_ipc='tx_batch_informer',
                 block_notifications_port=BLOCK_NOTIF_PORT, block_notifications_ipc='block_notifications',
                 tx_batcher_port=TX_BATCHER_PORT, tx_batcher_ipc='tx_batcher',
                 block_agg_controller_port=BLOCK_AGG_CONTROLLER_PORT, block_agg_controller_ipc='block_agg_controller',
                 incoming_work_port=INCOMING_WORK_PORT, incoming_work_ipc='incoming_work'
                 ):

        self.params = {
            ServiceType.PEER: (peer_port, peer_ipc),
            ServiceType.EVENT: (event_port, event_ipc),
            ServiceType.DISCOVERY: (discovery_port, discovery_ipc),
            ServiceType.BLOCK_SERVER: (block_port, block_ipc),
            ServiceType.SUBBLOCK_BUILDER_PUBLISHER: (sbb_pub_port, sbb_pub_ipc),
            ServiceType.BLOCK_AGGREGATOR: (block_agg_port, block_agg_ipc),
            ServiceType.TX_BATCH_INFORMER: (tx_batch_informer_port, tx_batch_informer_ipc),
            ServiceType.BLOCK_NOTIFICATIONS: (block_notifications_port, block_notifications_ipc),
            ServiceType.TX_BATCHER: (tx_batcher_port, tx_batcher_ipc),
            ServiceType.BLOCK_AGGREGATOR_CONTROLLER: (block_agg_controller_port, block_agg_controller_ipc),
            ServiceType.INCOMING_WORK: (incoming_work_port, incoming_work_ipc)
        }

    def resolve(self, socket_base, service_type, bind=False):
        port, ipc = self.params[service_type]
        return cilantro_ee.sockets.struct.resolve_tcp_or_ipc_base(socket_base, port, ipc, bind=bind)


class Parameters:
    def __init__(self,
                 socket_base: str,
                 ctx: zmq.asyncio.Context,
                 wallet,
                 network_parameters: NetworkParameters=NetworkParameters(),
                 debug=False,
                 masternode_contract=None,
                 delegate_contract=None
                 ):

        self.socket_base = socket_base
        self.ctx = ctx
        self.wallet = wallet
        self.network_parameters = network_parameters

        self.peer_service_address = self.network_parameters.resolve(socket_base, ServiceType.PEER)
        self.sockets = {}

        self.masternode_contract = masternode_contract
        self.delegate_contract = delegate_contract

        self.log = get_logger('Parameters')
        self.log.propagate = debug

    def get_masternode_sockets(self, service=None):
        masternodes = {}
        vks = set(self.masternode_contract.quick_read('S', 'members'))

        for k in self.sockets.keys():
            if k in vks:
                v = self.sockets.get(k)
                if v is None:
                    return

                if service is not None:
                    v = self.network_parameters.resolve(v, service)

                masternodes[k] = v

        return masternodes

    def get_masternode_vks(self):
        vks = set(self.masternode_contract.quick_read('S', 'members'))
        online_nodes = set(self.sockets.keys())
        return vks.intersection(online_nodes)

    def get_delegate_sockets(self, service=None):
        delegates = {}
        vks = set(self.delegate_contract.quick_read('S', 'members'))

        for k in self.sockets.keys():
            if k in vks:
                v = self.sockets.get(k)
                if v is None:
                    return

                if service is not None:
                    v = self.network_parameters.resolve(v, service)

                delegates[k] = v

        return delegates

    def get_all_sockets(self, service=None):
        all = {}

        for k, v in self.sockets.items():
            if service is None:
                all[k] = v
            else:
                all[k] = self.network_parameters.resolve(v, service)

        return all

    def resolve_vk(self, vk, service=None):
        socket = self.sockets.get(vk)

        if socket is None:
            return

        if service is None:
            return socket

        return self.network_parameters.resolve(socket, service)

    async def refresh(self):
        pb_nodes = set(self.delegate_contract.quick_read('S', 'members') + self.masternode_contract.quick_read('S', 'members'))
        self.log.info(f'Finding these nodes: {pb_nodes}')

        try:
            pb_nodes.remove(self.wallet.verifying_key().hex())
        except KeyError:
            pass

        current_nodes = set(self.sockets.keys())

        # Delete / remove old nodes
        to_del = self.old_nodes(pb_nodes, current_nodes)

        for node in to_del:
            self.remove_node(node)

        # Add new nodes
        # to_add = self.new_nodes(pb_nodes, current_nodes)

        coroutines = [self.find_node(m) for m in pb_nodes]

        tasks = asyncio.gather(*coroutines)
        loop = asyncio.get_event_loop()

        if loop.is_running():
            results = await asyncio.ensure_future(tasks)
        else:
            results = loop.run_until_complete(tasks)

        for r in results:
            self.log.info(r)
            if r is not None:
                _r = json.loads(r)

                if len(_r) == 0:
                    break

                vk, socket = [(k, v) for k, v in _r.items()][0]

                self.log.info(f'Found {vk} : {socket}')

                self.sockets.update({vk: socket})
            self.log.info('Done finding.')

    async def find_node(self, node):
        find_message = ['find', node]
        find_message = json.dumps(find_message).encode()

        return await get(self.peer_service_address, msg=find_message, ctx=self.ctx, timeout=1000)

    @staticmethod
    def new_nodes(phone_book_nodes, current_nodes):
        return phone_book_nodes - current_nodes

    @staticmethod
    def old_nodes(phone_book_nodes, current_nodes):
        return current_nodes - phone_book_nodes

    def remove_node(self, vk):
        entry = self.sockets.get(vk)

        if entry is not None:
            #entry.close()
            del self.sockets[vk]
