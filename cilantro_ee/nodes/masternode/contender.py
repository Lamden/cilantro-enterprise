from contracting.db.encoder import encode, decode
from contracting.db.driver import ContractDriver

from cilantro_ee import router, storage
from cilantro_ee.crypto.canonical import merklize, block_from_subblocks
from cilantro_ee.crypto.wallet import verify
from cilantro_ee.logger.base import get_logger

import asyncio
import time


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


class SBCInbox(router.Processor):
    def __init__(self, driver: ContractDriver, expected_subblocks=4, debug=True, *args, **kwargs):
        self.q = []
        self.driver = driver
        self.expected_subblocks = expected_subblocks
        self.log = get_logger('SBC')
        self.log.propagate = debug
        super().__init__(*args, **kwargs)

    async def process_message(self, msg):
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


class PotentialSolution:
    def __init__(self, struct):
        self.struct = struct
        self.signatures = []

    @property
    def votes(self):
        return len(self.signatures)

    def struct_to_dict(self):
        subblock = {
            'input_hash': self.struct['input_hash'],
            'transactions': self.struct['transactions'],
            'merkle_leaves': self.struct['merkle_tree']['leaves'],
            'subblock': self.struct['subblock'],
            'previous': self.struct['previous'],
            'signatures': []
        }

        for sig in self.signatures:
            subblock['signatures'].append({
                'signature': sig[0],
                'signer': sig[1]
            })

        subblock['signatures'].sort(key=lambda i: i['signer'])

        return subblock


class SubBlockContender:
    def __init__(self, input_hash, index, total_contacts, required_consensus=0.66, adequate_consensus=0.51):
        self.input_hash = input_hash
        self.index = index

        self.potential_solutions = {}
        self.best_solution = None

        self.total_responses = 0
        self.total_contacts = total_contacts

        self.required_consensus = required_consensus
        self.adequate_consensus = adequate_consensus

    def add_potential_solution(self, sbc):
        result_hash = sbc['merkle_tree']['leaves'][0]

        # Create a new potential solution if it is a new result hash
        if self.potential_solutions.get(result_hash) is None:
            self.potential_solutions[result_hash] = PotentialSolution(struct=sbc)

        # Add the signature to the potential solution
        p = self.potential_solutions.get(result_hash)
        p.signatures.append((sbc['merkle_tree']['signature'], sbc['signer']))

        # Update the best solution if the current potential solution now has more votes
        if self.best_solution is None or p.votes > self.best_solution.votes:
            self.best_solution = p

        self.total_responses += 1

    @property
    def failed(self):
        # True if all responses are recorded and required consensus is not possible
        return self.total_responses >= self.total_contacts and \
               not self.has_required_consensus

    @property
    def has_required_consensus(self):
        if self.best_solution is None:
            return False

        if self.best_solution.votes / self.total_contacts < self.required_consensus:
            return False

        return True

    @property
    def has_adequate_consensus(self):
        if self.best_solution is None:
            return False

        if self.best_solution.votes / self.total_contacts < self.adequate_consensus:
            return False

        return True

    @property
    def serialized_solution(self):
        if not self.has_adequate_consensus:
            return None
        if self.failed:
            return None

        return self.best_solution.struct_to_dict()


class BlockContender:
    def __init__(self, total_contacts, total_subblocks, required_consensus=0.66, acceptable_consensus=0.5):
        self.total_contacts = total_contacts
        self.total_subblocks = total_subblocks

        self.required_consensus = required_consensus

        # Acceptable consensus forces a block to complete. Anything below this will fail.
        self.acceptable_consensus = acceptable_consensus

        # Create an empty list to store the contenders as they come in
        self.subblock_contenders = [None for _ in range(self.total_subblocks)]

        self.log = get_logger('AGG')

    def add_sbcs(self, sbcs):
        for sbc in sbcs:
            # If it's out of range, ignore
            if sbc['subblock'] > self.total_subblocks - 1:
                continue

            # If it's the first contender, create a new object and store it
            if self.subblock_contenders[sbc['subblock']] is None:
                self.log.info('First block. Making a new solution object.')
                s = SubBlockContender(
                    input_hash=sbc['input_hash'],
                    index=sbc['subblock'],
                    total_contacts=self.total_contacts
                )
                self.subblock_contenders[sbc['subblock']] = s

            # Access the object at the SB index and add a potential solution
            s = self.subblock_contenders[sbc['subblock']]
            s.add_potential_solution(sbc)

    def current_responded_sbcs(self):
        i = 0
        for s in self.subblock_contenders:
            if s is not None:
                i += 1

        return i

    def block_has_consensus(self):
        for sb in self.subblock_contenders:
            if sb is None:
                return False
            if not sb.has_required_consensus:
                return False

        return True

    def get_current_best_block(self):
        block = []

        # Where None is appended = failed
        for sb in self.subblock_contenders:
            if sb is None:
                self.log.error('SB IS NONE!!!')
                block.append(None)
            else:
                block.append(sb.serialized_solution)

        return block

    @property
    def responses(self):
        m = 0
        for sb in self.subblock_contenders:
            if sb is None:
                continue
            if sb.total_responses > m:
                m = sb.total_responses

        return m

# Can probably move this into the masternode. Move the sbc inbox there and deprecate this class
class Aggregator:
    def __init__(self, driver, expected_subblocks=4, seconds_to_timeout=10):
        self.expected_subblocks = expected_subblocks
        self.sbc_inbox = SBCInbox(
            driver=driver,
            expected_subblocks=self.expected_subblocks,
        )

        self.driver = driver

        self.seconds_to_timeout = seconds_to_timeout

        self.log = get_logger('AGG')

    async def gather_subblocks(self, total_contacts, quorum_ratio=0.66, adequate_ratio=0.5, expected_subblocks=4):
        self.sbc_inbox.expected_subblocks = expected_subblocks

        self.log.info(f'''
========
Gathering subblocks:
Total Contacts: {total_contacts}, Expected SBs: {expected_subblocks}
Quorum Ratio: {quorum_ratio}, Adequate Ratio: {adequate_ratio}
========
        ''')

        contenders = BlockContender(
            total_contacts=total_contacts,
            required_consensus=quorum_ratio,
            total_subblocks=expected_subblocks,
            acceptable_consensus=adequate_ratio
        )

        # Add timeout condition.
        started = time.time()
        while (not contenders.block_has_consensus() and contenders.responses < contenders.total_contacts) and \
                time.time() - started < self.seconds_to_timeout:

            if self.sbc_inbox.has_sbc():
                sbcs = await self.sbc_inbox.receive_sbc() # Can probably make this raw sync code
                self.log.info('Pop it in there.')
                contenders.add_sbcs(sbcs)
            await asyncio.sleep(0)

        if time.time() - started > self.seconds_to_timeout:
            self.log.error('BLOCK TIMEOUT!')

        self.log.info('Done aggregating new block.')

        block = contenders.get_current_best_block()

        return block_from_subblocks(
            block,
            previous_hash=storage.get_latest_block_hash(self.driver),
            block_num=storage.get_latest_block_height(self.driver) + 1
        )