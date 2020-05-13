from cilantro_ee.inbox import JSONAsyncInbox
import zmq.asyncio
from contracting.db.encoder import encode
from zmq.error import ZMQBaseError
from contracting.db.encoder import decode
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
