from cilantro_ee.nodes.masternode import masternode
from cilantro_ee.nodes import base
from cilantro_ee import router, storage

import zmq.asyncio
import asyncio

from unittest import TestCase

class TestBlockService(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init_router_and_add_service(self):
        r = router.Router(
            socket_id='tcp://127.0.0.1:18001',
            ctx=self.ctx
        )

        b = masternode.BlockService(
            blocks=storage.BlockStorage(),
            driver=storage.StateDriver()
        )

        r.add_service(base.BLOCK_SERVICE, b)
