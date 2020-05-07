from cilantro_ee.sockets.inbox import SecureAsyncInbox
from cilantro_ee.logger.base import get_logger
from contracting.db.encoder import decode


class WorkInbox(SecureAsyncInbox):
    def __init__(self, debug=True, *args, **kwargs):
        self.work = {}

        self.todo = []
        self.accepting_work = False

        self.log = get_logger('DEL WI')
        self.log.propagate = debug

        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        self.log.info('Got some work.')

        msg = decode(msg.decode())

        if not self.accepting_work:
            self.log.info('TODO')
            self.todo.append(msg)

        else:
            self.verify_work(msg)

        await super().handle_msg(_id, b'OK')

    def verify_work(self, msg):
        self.work[msg['sender']] = msg

    def process_todo_work(self):
        self.log.info(f'Current todo {self.todo}')

        for work in self.todo:
            self.verify_work(work)

        self.todo.clear()
