from cilantro_ee.sockets.services import get
from cilantro_ee.sockets.inbox import AsyncInbox
from cilantro_ee.logger.base import get_logger
from cilantro_ee.storage import CilantroStorageDriver, BlockchainDriver
import zmq.asyncio
import json

from cilantro_ee.formatting import primatives

GET_BLOCK = 'get_block'
GET_HEIGHT = 'get_height'


class BlockServer(AsyncInbox):
    def __init__(self, blocks: CilantroStorageDriver=None, driver=BlockchainDriver(), *args, **kwargs):
        self.blocks = blocks
        self.driver = driver
        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        command = json.loads(msg.decode())

        response = {}
        if primatives.dict_has_keys(command, keys={'name', 'arg'}):
            if command['name'] == GET_BLOCK:
                response = self.get_block(command)
            elif command['name'] == GET_HEIGHT:
                response = self.driver.get_latest_block_num()

        await super().handle_msg(_id, response)

    def get_block(self, command):
        num = command.get('arg')
        if not primatives.number_is_formatted(num):
            return {}

        block = self.blocks.get_block(num)

        if block is None:
            return {}

        return block


class BlockFetcher:
    def __init__(self, ctx: zmq.asyncio.Context):

        self.ctx = ctx
        self.log = get_logger('Catchup')

    async def get_latest_block_height(self, socket):
        msg = {
            'name': GET_HEIGHT,
            'arg': ''
        }

        response = await get(
            socket_id=socket,
            msg=json.dumps(msg),
            ctx=self.ctx,
            timeout=1000,
            retries=0,
            dealer=True
        )

        return response

    async def get_block_from_master(self, i: int, socket):
        msg = {
            'name': GET_BLOCK,
            'arg': i
        }

        response = await get(
            socket_id=socket,
            msg=json.dumps(msg),
            ctx=self.ctx,
            timeout=1000,
            retries=0,
            dealer=True
        )

        return response
