import asyncio
from cilantro_ee.crypto.wallet import Wallet
import zmq
import zmq.asyncio
from contracting.db.encoder import encode, decode
from zmq.error import ZMQBaseError
# new block
# work
# sub block contenders
# ping
# join

# join should send messages to other people if they are not in the peer list
# ping returns pepper for id verification

OK = {
    'response': 'ok'
}


def build_message(service, message):
    return {
        'service': service,
        'msg': message
    }


class Processor:
    async def process_message(self, msg):
        raise NotImplementedError


class QueueProcessor(Processor):
    def __init__(self):
        self.q = []

    async def process_message(self, msg):
        self.q.append(msg)


'''
Router takes messages in the following format:
{
    'service': <name of service as string>,
    'msg': {
        <any JSON payload here>
    }
}
It then sends the msg to the registered 'processor' and returns
a message to the requester.
'''


class AsyncInbox:
    def __init__(self, socket_id, ctx: zmq.Context, wallet=None, linger=1000, poll_timeout=50):
        self.address = socket_id
        self.wallet = wallet

        self.ctx = ctx

        self.socket = None

        self.linger = linger
        self.poll_timeout = poll_timeout

        self.running = False

    async def serve(self):
        self.setup_socket()

        self.running = True

        while self.running:
            try:
                event = await self.socket.poll(timeout=self.poll_timeout, flags=zmq.POLLIN)
                if event:
                    _id, msg = await self.receive_message()
                    asyncio.ensure_future(self.handle_msg(_id, msg))

            except zmq.error.ZMQError as e:
                self.socket.close()
                self.setup_socket()

        self.socket.close()

    async def receive_message(self):
        _id = await self.socket.recv()
        msg = await self.socket.recv()

        return _id, msg

    async def handle_msg(self, _id, msg):
        await self.return_msg(_id, msg)

    async def return_msg(self, _id, msg):
        sent = False
        while not sent:
            try:
                await self.socket.send_multipart([_id, msg])
                sent = True
            except zmq.error.ZMQError:
                self.socket.close()
                self.setup_socket()

    def setup_socket(self):
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.setsockopt(zmq.LINGER, self.linger)
        self.socket.bind(self.address)

    def stop(self):
        self.running = False


class JSONAsyncInbox(AsyncInbox):
    def __init__(self, secure=False, *args, **kwargs):
        self.secure = secure
        super().__init__(*args, **kwargs)

    def setup_socket(self):
        self.socket = self.ctx.socket(zmq.ROUTER)

        if self.secure:
            self.socket.curve_secretkey = self.wallet.curve_sk
            self.socket.curve_publickey = self.wallet.curve_vk

            self.socket.curve_server = True

        self.socket.setsockopt(zmq.LINGER, self.linger)
        self.socket.bind(self.address)

    async def receive_message(self):
        _id = await self.socket.recv()
        msg = await self.socket.recv()

        return _id, decode(msg)

    async def return_msg(self, _id, msg):
        msg = encode(msg).encode()
        await super().return_msg(_id, msg)


class Router(JSONAsyncInbox):
    def __init__(self, *args, **kwargs):
        self.services = {}

        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        service = msg.get('service')
        request = msg.get('msg')

        if service is None:
            await super().return_msg(_id, OK)
            return

        if request is None:
            await super().return_msg(_id, OK)
            return

        processor = self.services.get(service)

        if processor is None:
            await super().return_msg(_id, OK)
            return

        response = await processor.process_message(request)

        if response is None:
            await super().return_msg(_id, OK)
            return

        await super().return_msg(_id, response)

    def add_service(self, name: str, processor: Processor):
        self.services[name] = processor


def build_socket(socket_str: str, ctx: zmq.asyncio.Context, linger=500):
    socket = ctx.socket(zmq.DEALER)
    socket.setsockopt(zmq.LINGER, linger)
    socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

    try:
        socket.connect(socket_str)
        return socket
    except ZMQBaseError:
        return None


# def build_secure_socket(socket_str: str, wallet: Wallet, reciever_vk: str, ctx: zmq.asyncio.Context, linger=500):
#     socket = ctx.socket(zmq.DEALER)
#     socket.setsockopt(zmq.LINGER, linger)
#     socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
#
#     socket.curve_secretkey = wallet.curve_sk
#     socket.curve_publickey = wallet.curve_vk
#
#     server_pub, _ = load_certificate(str(cert_dir / f'{server_vk}.key'))
#
#     socket.curve_serverkey = server_pub
#
#     try:
#         socket.connect(socket_str)
#     except ZMQBaseError:
#         return None


async def request(socket_str: str, service: str, msg: dict, ctx: zmq.asyncio.Context, timeout=1000, linger=500):
    socket = ctx.socket(zmq.DEALER)
    socket.setsockopt(zmq.LINGER, linger)
    socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

    try:
        socket.connect(socket_str)
    except ZMQBaseError:
        return None

    message = {
        'service': service,
        'msg': msg
    }

    payload = encode(message).encode()

    await socket.send(payload)

    event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
    msg = None
    if event:
        response = await socket.recv()

        msg = decode(response)

        socket.close()

    return msg

