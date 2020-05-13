from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver
from cilantro_ee.logger.base import get_logger

from decimal import Decimal
import decimal
from contracting.stdlib.bridge.decimal import ContractingDecimal

decimal.getcontext().rounding = decimal.ROUND_DOWN

REQUIRED_CONTRACTS = [
    'stamp_cost',
    'rewards',
    'currency',
    'election_house',
    'foundation',
    'masternodes',
    'delegates'
]
DUST_EXPONENT = 8


def contract_exists(name: str, client: ContractingClient):
    return client.get_contract(name) is not None


def is_setup(client: ContractingClient):
    for contract in REQUIRED_CONTRACTS:
        if not contract_exists(contract, client):
            return False
    return True


def stamps_in_block(block):
    total = 0

    for sb in block['subblocks']:
        for tx in sb['transactions']:
            total += tx['stamps_used']

    return total


def add_to_balance(vk, amount, client: ContractingClient):
    current_balance = client.get_var(contract='currency', variable='balances', arguments=[vk], mark=False)

    if current_balance is None:
        current_balance = ContractingDecimal(0)

    amount = ContractingDecimal(amount)

    client.set_var(
        contract='currency',
        variable='balances',
        arguments=[vk],
        value=amount + current_balance,
        mark=True
    )


def calculate_participant_reward(participant_ratio, number_of_participants, total_tau_to_split):
    reward = (Decimal(participant_ratio) / number_of_participants) * total_tau_to_split
    rounded_reward = round(reward, DUST_EXPONENT)
    return rounded_reward


def calculate_all_rewards(total_tau_to_split, client: ContractingClient):
    master_ratio, delegate_ratio, burn_ratio, foundation_ratio = \
        client.get_var(contract='rewards', variable='S', arguments=['value'])

    master_reward = calculate_participant_reward(
        participant_ratio=master_ratio,
        number_of_participants=len(client.get_var(contract='masternodes', variable='S', arguments=['members'])),
        total_tau_to_split=total_tau_to_split
    )

    delegate_reward = calculate_participant_reward(
        participant_ratio=delegate_ratio,
        number_of_participants=len(client.get_var(contract='delegates', variable='S', arguments=['members'])),
        total_tau_to_split=total_tau_to_split
    )

    foundation_reward = calculate_participant_reward(
        participant_ratio=foundation_ratio,
        number_of_participants=1,
        total_tau_to_split=total_tau_to_split
    )

    # burn does nothing, as the stamps are already deducted from supply

    return master_reward, delegate_reward, foundation_reward


def distribute_rewards(master_reward, delegate_reward, foundation_reward, client: ContractingClient):
    for m in client.get_var(contract='masternodes', variable='S', arguments=['members']):
        add_to_balance(vk=m, amount=master_reward, client=client)

    for d in client.get_var(contract='delegates', variable='S', arguments=['members']):
        add_to_balance(vk=d, amount=delegate_reward, client=client)

    foundation_wallet = client.get_var(contract='foundation', variable='owner')
    add_to_balance(vk=foundation_wallet, amount=foundation_reward, client=client)


def issue_rewards(block, client: ContractingClient):
    total_tau_to_split = stamps_in_block(block) / client.get_var(contract='stamp_cost', variable='S', arguments=['value'])

    rewards = calculate_all_rewards(
        total_tau_to_split=total_tau_to_split,
        client=client
    )

    distribute_rewards(*rewards, client=client)


class RewardManager:
    def __init__(self, driver=ContractDriver(), debug=True):
        self.driver = driver
        self.client = ContractingClient(driver=driver)

        # All of this can be just derived from the blockchain driver without marking reads
        # Should marks on default be false?
        self.stamp_contract = self.client.get_contract('stamp_cost')
        self.reward_contract = self.client.get_contract('rewards')
        self.currency_contract = self.client.get_contract('currency')
        self.election_house = self.client.get_contract('election_house')
        self.foundation_contract = self.client.get_contract('foundation')
        self.masternodes_contract = self.client.get_contract('masternodes')
        self.delegates_contract = self.client.get_contract('delegates')

        assert self.stamp_contract is not None, 'Stamp contract not in state.'
        assert self.reward_contract is not None, 'Reward contract not in state.'
        assert self.currency_contract is not None, 'Currency contract not in state.'
        assert self.foundation_contract is not None, 'Foundation contract not in state.'
        assert self.masternodes_contract is not None, 'Masternodes not in state.'
        assert self.delegates_contract is not None, 'Delegates not in state.'

        self.log = get_logger('RWM')
        self.log.propagate = debug

        self.dust_exponent = 8

    def issue_rewards(self, block):
        # ratio / total participants = % of total
        master_ratio, delegate_ratio, burn_ratio, foundation_ratio = self.reward_ratio

        stamps = self.stamps_in_block(block)

        self.log.info(f'{stamps} stamps in this block to issue.')

        pending_rewards = self.stamps_in_block(block) / self.stamps_per_tau

        self.log.info(f'{pending_rewards} tau in this block to issue.')

        masters = self.masternodes_contract.quick_read('S', 'members')
        delegates = self.delegates_contract.quick_read('S', 'members')

        total_shares = len(masters) + len(delegates) + 1 + 1

        reward_share = Decimal(str(pending_rewards / total_shares))

        master_reward = reward_share * Decimal(str(master_ratio))
        delegate_reward = reward_share * Decimal(str(delegate_ratio))
        foundation_reward = reward_share * Decimal(str(foundation_ratio))
        # BURN + DEVELOPER

        decimal.getcontext().rounding = decimal.ROUND_DOWN

        master_reward = round(master_reward, self.dust_exponent)
        delegate_reward = round(delegate_reward, self.dust_exponent)
        foundation_reward = round(foundation_reward, self.dust_exponent)

        for m in masters:
            self.add_to_balance(vk=m, amount=master_reward)

        for d in delegates:
            self.add_to_balance(vk=d, amount=delegate_reward)

        self.add_to_balance(vk=self.foundation_contract.owner.get(), amount=foundation_reward)

    def add_to_balance(self, vk, amount):
        current_balance = self.driver.get_var(contract='currency', variable='balances', arguments=[vk], mark=False)

        if current_balance is None:
            current_balance = ContractingDecimal(0)

        amount = ContractingDecimal(amount)
        self.log.info('Sending {} to {}. New bal: {} -> {}'.format(amount, vk[:8], current_balance, amount + current_balance))

        self.driver.set_var(
            contract='currency',
            variable='balances',
            arguments=[vk],
            value=amount + current_balance,
            mark=True
        )

        # This should only happen once on the nodes
        self.driver.commit()
        self.driver.clear_pending_state()

    # def get_pending_rewards(self):
    #     key = self.driver.get(PENDING_REWARDS_KEY)
    #
    #     if key is None:
    #         key = 0
    #
    #     return key

    # def set_pending_rewards(self, value):
    #     self.driver.set(PENDING_REWARDS_KEY, value=value, mark=False)

    @property
    def stamps_per_tau(self):
        return self.stamp_contract.quick_read('S', 'value')

    @staticmethod
    def stamps_in_block(block):
        total = 0

        for sb in block['subblocks']:
            for tx in sb['transactions']:
                total += tx['stamps_used']

        return total

    @property
    def reward_ratio(self):
        return self.reward_contract.quick_read(variable='S', args=['value'])
