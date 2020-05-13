from cilantro_ee.router import request, Processor
from cilantro_ee.storage import MasterStorage, BlockchainDriver
import zmq.asyncio

from cilantro_ee.formatting import primatives

GET_BLOCK = 'get_block'
GET_HEIGHT = 'get_height'

BLOCK_SERVICE = 'service'


class BlockService(Processor):
    def __init__(self, blocks: MasterStorage=None, driver=BlockchainDriver()):
        self.blocks = blocks
        self.driver = driver

    async def process_message(self, msg):
        response = {}
        if primatives.dict_has_keys(msg, keys={'name', 'arg'}):
            if msg['name'] == GET_BLOCK:
                response = self.get_block(msg)
            elif msg['name'] == GET_HEIGHT:
                response = self.driver.get_latest_block_num()

        return response

    def get_block(self, command):
        num = command.get('arg')
        if not primatives.number_is_formatted(num):
            return {}

        block = self.blocks.get_block(num)

        if block is None:
            return {}

        return block


async def get_latest_block_height(ip_string: str, ctx: zmq.asyncio.Context):
    msg = {
        'name': GET_HEIGHT,
        'arg': ''
    }

    response = await request(
        socket_str=ip_string,
        service=BLOCK_SERVICE,
        msg=msg,
        ctx=ctx
    )

    return response


async def get_block(block_num: int, ip_string: str, ctx: zmq.asyncio.Context):
    msg = {
        'name': GET_BLOCK,
        'arg': block_num
    }

    response = await request(
        socket_str=ip_string,
        service=BLOCK_SERVICE,
        msg=msg,
        ctx=ctx
    )

    return response
