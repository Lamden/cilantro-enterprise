import asyncio

from cilantro_ee.crypto.canonical import merklize
from cilantro_ee.crypto.wallet import verify
from cilantro_ee.logger.base import get_logger
from cilantro_ee.inbox import SecureAsyncInbox
from cilantro_ee.storage import BlockchainDriver
from contracting.db.encoder import encode, decode


class SBCInbox(SecureAsyncInbox):
    def __init__(self, driver: BlockchainDriver, expected_subblocks=4, debug=True, *args, **kwargs):
        self.q = []
        self.driver = driver
        self.expected_subblocks = expected_subblocks
        self.log = get_logger('SBC')
        self.log.propagate = debug
        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        msg = decode(msg.decode())

        # Ignore bad message types
        # Ignore if not enough subblocks
        # Make sure all the contenders are valid
        all_valid = True
        for i in range(len(msg)):
            try:
                self.sbc_is_valid(msg[i], i)
            except SBCException as e:
                self.log.error(type(e))
                all_valid = False

        # Add the whole contender
        if all_valid:
            self.q.append(msg)
            self.log.info('Added new SBC')

    def sbc_is_valid(self, sbc, sb_idx=0):
        if sbc['subblock'] != sb_idx:
            raise SBCIndexMismatchError

        # Make sure signer is in the delegates
        if len(sbc['transactions']) == 0:
            msg = sbc['input_hash']
        else:
            msg = sbc['merkle_tree']['leaves'][0]

        valid_sig = verify(
            vk=sbc['signer'],
            msg=msg,
            signature=sbc['merkle_tree']['signature']
        )

        if not valid_sig:
            raise SBCInvalidSignatureError

        if len(sbc['merkle_tree']['leaves']) > 0:
            txs = [encode(tx).encode() for tx in sbc['transactions']]
            expected_tree = merklize(txs)

            for i in range(len(expected_tree)):
                if expected_tree[i] != sbc['merkle_tree']['leaves'][i]:
                    raise SBCMerkleLeafVerificationError

    def has_sbc(self):
        return len(self.q) > 0

    async def receive_sbc(self):
        self.log.info('Waiting for an SBC...')
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        self.log.info('Got one! Returning...')
        return self.q.pop(0)


class SBCException(Exception):
    pass


class SBCBadMessage(SBCException):
    pass


class SBCInvalidSignatureError(SBCException):
    pass


class SBCBlockHashMismatchError(SBCException):
    pass


class SBCMerkleLeafVerificationError(SBCException):
    pass


class SBCIndexMismatchError(SBCException):
    pass


class SBCIndexGreaterThanPossibleError(SBCException):
    pass