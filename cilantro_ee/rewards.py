import decimal

from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.client import ContractingClient

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
    reward = (decimal.Decimal(str(participant_ratio)) / number_of_participants) * decimal.Decimal(str(total_tau_to_split))
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


def calculate_tau_to_split(block, client: ContractingClient):
    return stamps_in_block(block) / client.get_var(contract='stamp_cost', variable='S', arguments=['value'])


def issue_rewards(block, client: ContractingClient):
    total_tau_to_split = calculate_tau_to_split(block, client)

    rewards = calculate_all_rewards(
        total_tau_to_split=total_tau_to_split,
        client=client
    )

    distribute_rewards(*rewards, client=client)
