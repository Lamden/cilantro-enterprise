import asyncio

from cilantro_ee.sockets.inbox import SecureAsyncInbox
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.logger.base import get_logger
from contracting.db.encoder import decode


class NBNInbox(SecureAsyncInbox):
    def __init__(self, driver: BlockchainDriver=BlockchainDriver(), *args, **kwargs):
        self.q = []
        self.driver = driver
        self.log = get_logger('NBN')
        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        self.q.append(decode(msg.decode()))
        await super().handle_msg(_id, b'OK')

    async def wait_for_next_nbn(self):
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        nbn = self.q.pop(0)

        self.q.clear()

        return nbn

    def clean(self):
        self.q = [nbn for nbn in self.q if nbn['blockNum'] >= self.driver.latest_block_num]

