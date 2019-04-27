from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.utils import lazy_property
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES
from cilantro_ee.messages.block_data.sub_block import SubBlock
from cilantro_ee.messages.utils import validate_hex
from cilantro_ee.messages.block_data.block_data import BlockData
from typing import List
from cilantro_ee.storage.vkbook import VKBook
from random import choice
from string import ascii_letters, digits

import blockdata_capnp


class BlockNotification(MessageBase):

    def validate(self):
        # TODO clean this up, and share subclass with BlockMetaData. Then we can do deep validation in one place
        assert validate_hex(self.block_hash, 64), 'Invalid block hash {}'.format(self.block_hash)
        assert validate_hex(self._data.prevBlockHash, 64), 'Invalid previous block hash'
        assert self.block_num > 0, "Block num must be greater than or equal to 0"

    @classmethod
    def _deserialize_data(cls, data):
        return blockdata_capnp.BlockNotification.from_bytes_packed(data)

    @classmethod
    def from_dict(cls, data: dict):
        struct = blockdata_capnp.BlockNotification.new_message(**data)
        return cls.from_data(struct)

    @classmethod
    def create(cls, prev_block_hash: str, block_hash: str, block_num: int,
                    block_owners: List[str], input_hashes: List[set]):

        struct = blockdata_capnp.BlockNotification.new_message()
        struct.prevBlockHash = prev_block_hash
        struct.blockHash = block_hash
        struct.blockNum = block_num
        struct.blockOwners = block_owners
        struct.inputHashes = input_hashes

        return cls.from_data(struct)

    @lazy_property
    def prev_block_hash(self) -> str:
        return self._data.prevBlockHash

    @lazy_property
    def block_hash(self) -> str:
        return self._data.blockHash

    @property
    def block_num(self) -> int:
        return self._data.blockNum

    @lazy_property
    def block_owners(self) -> List[str]:
        return [x for x in self._data.blockOwners]  # Necessary to cast capnp list builder to Python list

    @lazy_property
    def input_hashes(self) -> List[set]:
        return [x for x in self._data.inputHashes]  # Necessary to cast capnp list builder to Python list

    def __repr__(self):
        # return "<{} (block_hash={}, block_num={}, prev_b_hash={}, input_hashes={}, block_owners={})>"\
            # .format(type(self), self.block_hash, self.block_num, self.prev_block_hash, self.input_hashes, self.block_owners))
        return f"{type(self)} (block_hash={self.block_hash}, block_num={self.block_num}, \
                 prev_b_hash={self.prev_block_hash}, input_hashes={self.input_hashes}, block_owners={self.block_owners})>"


class NewBlockNotification(BlockNotification):
    pass

class EmptyBlockNotification(BlockNotification):
    pass

# turn input_hashes as list of lists for this
class FailedBlockNotification(BlockNotification):
    pass

class BlockNotificationBuilder:
    MN_SK = TESTNET_MASTERNODES[0]['sk'] if len(TESTNET_MASTERNODES) > 0 else 'A' * 64
    MN_VK = TESTNET_MASTERNODES[0]['vk'] if len(TESTNET_MASTERNODES) > 0 else 'A' * 64
    GENESIS_BLOCK_HASH = '0' * 64

    @classmethod
    def create_random_notification(cls, prev_hash: str=GENESIS_BLOCK_HASH, num: int=1) -> BlockNotification:
        from cilantro_ee.messages.block_data.sub_block import SubBlockBuilder

        input_hash1 = ''.join(choice(ascii_letters + digits) for i in range(64))
        input_hash2 = ''.join(choice(ascii_letters + digits) for i in range(64))
        sb1 = SubBlockBuilder.create(input_hash=input_hash1, idx=0)
        sb2 = SubBlockBuilder.create(input_hash=input_hash2, idx=1)
        sbs = [sb1, sb2]

        block_hash = BlockData.compute_block_hash([sb1.merkle_root, sb2.merkle_root], prev_hash)
        block_num = num
        block_owners = [m['vk'] for m in TESTNET_MASTERNODES]  #[cls.MN_VK]

        block = BlockNotification.create(block_hash=block_hash, prev_block_hash=prev_hash, block_num=block_num,
                                 sub_blocks=sbs, block_owners=block_owners)

        return block

    @classmethod
    def create_conseq_notifications(cls, num_blocks: int, first_hash=GENESIS_BLOCK_HASH, first_num=1):
        curr_num, curr_hash = first_num, first_hash
        blocks = []
        for _ in range(num_blocks):
            block = cls.create_random_notification(curr_hash, curr_num)
            curr_num += 1
            curr_hash = block.block_hash
            blocks.append(block)
        return blocks

