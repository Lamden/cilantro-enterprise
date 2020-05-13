import asyncio

import zmq

from cilantro_ee.struct import SocketStruct, Protocols
from contracting.db.encoder import encode, decode


class AsyncInbox:
    def __init__(self, socket_id: SocketStruct, ctx: zmq.Context, wallet=None, linger=1000, poll_timeout=50):
        if socket_id.protocol == Protocols.TCP:
            socket_id.id = '*'

        self.address = str(socket_id)
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


class SecureAsyncInbox(AsyncInbox):
    def setup_socket(self):
        self.socket = self.ctx.socket(zmq.ROUTER)

        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk

        self.socket.curve_server = True

        self.socket.setsockopt(zmq.LINGER, self.linger)
        self.socket.bind(self.address)


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
