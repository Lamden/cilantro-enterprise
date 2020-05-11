from cilantro_ee.sockets.inbox import SecureAsyncInbox
from contracting.db.encoder import decode

# new block
# work
# sub block contenders
# ping
# join

# join should send messages to other people if they are not in the peer list
# ping returns pepper for id verification

OK = b'OK'

EXAMPLE_MESSAGE = {
    'inbox': 'some_id',
    'msg': {

    }
}


class Processor:
    async def process_message(self, msg):
        raise NotImplementedError


class Router(SecureAsyncInbox):
    def __init__(self, *args, **kwargs):
        self.services = {}

        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        decoded_msg = decode(msg)

        inbox = decoded_msg.get('inbox')
        request = decoded_msg.get('msg')

        if inbox is None:
            await super().return_msg(_id, OK)

        if request is None:
            await super().return_msg(_id, OK)

        processor = self.services.get(inbox)

        if processor is None:
            await super().return_msg(_id, OK)

        response = await processor.process_message(request)

        if response is None:
            await super().return_msg(_id, OK)

        await super().return_msg(_id, response)

    def register_service(self, name: str, processor: Processor):
        self.services[name] = processor
