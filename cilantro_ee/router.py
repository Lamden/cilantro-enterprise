from cilantro_ee.inbox import JSONAsyncInbox

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
        inbox = msg.get('inbox')
        request = msg.get('msg')

        if inbox is None:
            await super().return_msg(_id, OK)
            return

        if request is None:
            await super().return_msg(_id, OK)
            return

        processor = self.services.get(inbox)

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
