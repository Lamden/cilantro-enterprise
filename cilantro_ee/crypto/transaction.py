import time

from cilantro_ee.crypto.canonical import format_dictionary
from cilantro_ee.formatting import check_format, rules, primatives
from contracting.db.encoder import encode
from cilantro_ee import storage
from cilantro_ee.crypto import wallet
from contracting.client import ContractingClient


class TransactionException(Exception):
    pass


class TransactionSignatureInvalid(TransactionException):
    pass


class TransactionPOWProofInvalid(TransactionException):
    pass


class TransactionProcessorInvalid(TransactionException):
    pass


class TransactionTooManyPendingException(TransactionException):
    pass


class TransactionNonceInvalid(TransactionException):
    pass


class TransactionStampsNegative(TransactionException):
    pass


class TransactionSenderTooFewStamps(TransactionException):
    pass


class TransactionContractNameInvalid(TransactionException):
    pass


class TransactionFormattingError(TransactionException):
    pass


EXCEPTION_MAP = {
    TransactionNonceInvalid: {'error': 'Transaction nonce is invalid.'},
    TransactionProcessorInvalid: {'error': 'Transaction processor does not match expected processor.'},
    TransactionTooManyPendingException: {'error': 'Too many pending transactions currently in the block.'},
    TransactionSenderTooFewStamps: {'error': 'Transaction sender has too few stamps for this transaction.'},
    TransactionPOWProofInvalid: {'error': 'Transaction proof of work is invalid.'},
    TransactionSignatureInvalid: {'error': 'Transaction is not signed by the sender.'},
    TransactionStampsNegative: {'error': 'Transaction has negative stamps supplied.'},
    TransactionException: {'error': 'Another error has occured.'},
    TransactionFormattingError: {'error': 'Transaction is not formatted properly.'}
}


def check_tx_formatting(tx: dict, expected_processor: str):
    if not check_format(tx, rules.TRANSACTION_RULES):
        raise TransactionFormattingError

    if not wallet.verify(
            tx['payload']['sender'],
            encode(tx['payload']),
            tx['metadata']['signature']
    ):
        raise TransactionSignatureInvalid

    if tx['payload']['processor'] != expected_processor:
        raise TransactionProcessorInvalid


def get_nonces(sender, processor, driver: storage.NonceStorage):
    nonce = driver.get_nonce(
        processor=processor,
        sender=sender
    )

    if nonce is None:
        nonce = 0

    pending_nonce = driver.get_pending_nonce(
        processor=processor,
        sender=sender
    )
    if pending_nonce is None:
        pending_nonce = 0

    return nonce, pending_nonce


def get_new_pending_nonce(tx_nonce, nonce, pending_nonce, strict=True, tx_per_block=15):
    # Attempt to get the current block's pending nonce
    if tx_nonce - nonce > tx_per_block or pending_nonce - nonce >= tx_per_block:
        raise TransactionTooManyPendingException

    expected_nonce = max(nonce, pending_nonce)

    if strict:
        if tx_nonce != expected_nonce:
            raise TransactionNonceInvalid
        expected_nonce += 1

    else:
        if tx_nonce < expected_nonce:
            raise TransactionNonceInvalid
        expected_nonce = tx_nonce + 1

    return expected_nonce


def has_enough_stamps(balance, stamps_per_tau, stamps_supplied, contract=None, function=None, amount=0):
    if balance * stamps_per_tau < stamps_supplied:
        raise TransactionSenderTooFewStamps

    # Prevent people from sending their entire balances for free by checking if that is what they are doing.
    if contract == 'currency' and function == 'transfer':

        # If you have less than 2 transactions worth of tau after trying to send your amount, fail.
        if ((balance - amount) * stamps_per_tau) / 6000 < 2:
            raise TransactionSenderTooFewStamps


def contract_name_is_valid(contract, function, name):
    if contract == 'submission' and function == 'submit_contract' and not primatives.contract_name_is_formatted(name):
        raise TransactionContractNameInvalid


def transaction_is_not_expired(transaction, timeout=5):
    timestamp = transaction['metadata']['timestamp']
    return (int(time.time()) - timestamp) < timeout


def build_transaction(wallet, contract: str, function: str, kwargs: dict, nonce: int, processor: str, stamps: int):
    payload = {
        'contract': contract,
        'function': function,
        'kwargs': kwargs,
        'nonce': nonce,
        'processor': processor,
        'sender': wallet.verifying_key,
        'stamps_supplied': stamps,
    }

    assert check_format(payload, rules.TRANSACTION_PAYLOAD_RULES), 'Invalid payload provided!'

    signature = wallet.sign(encode(payload))

    metadata = {
        'signature': signature,
        'timestamp': int(time.time())
    }

    tx = {
        'payload': payload,
        'metadata': metadata
    }

    return encode(format_dictionary(tx))


# Run through all tests
def transaction_is_valid(transaction, expected_processor, client: ContractingClient, nonces: storage.NonceStorage, strict=True,
                         tx_per_block=15, timeout=5):
    # Check basic formatting so we can access via __getitem__ notation without errors
    if not check_format(transaction, rules.TRANSACTION_RULES):
        return TransactionFormattingError

    transaction_is_not_expired(transaction, timeout)

    # Put in to variables for visual ease
    processor = transaction['payload']['processor']
    sender = transaction['payload']['sender']

    # Checks if correct processor and if signature is valid
    check_tx_formatting(transaction, expected_processor)

    # Gets the expected nonces
    nonce, pending_nonce = get_nonces(sender, processor, nonces)

    # Get the provided nonce
    tx_nonce = transaction['payload']['nonce']

    # Check to see if the provided nonce is valid to what we expect and
    # if there are less than the max pending txs in the block
    get_new_pending_nonce(tx_nonce, nonce, pending_nonce, strict=strict, tx_per_block=tx_per_block)

    # Get the senders balance and the current stamp rate
    balance = client.get_var(contract='currency', variable='balances', arguments=[sender], mark=False)
    stamp_rate = client.get_var(contract='stamp_cost', variable='S', arguments=['value'], mark=False)

    contract = transaction['payload']['contract']
    func = transaction['payload']['function']
    stamps_supplied = transaction['payload']['stamps_supplied']
    if stamps_supplied is None:
        stamps_supplied = 0

    if stamp_rate is None:
        stamp_rate = 0

    if balance is None:
        balance = 0

    # Get how much they are sending
    amount = transaction['payload']['kwargs'].get('amount')
    if amount is None:
        amount = 0

    # Check if they have enough stamps for the operation
    has_enough_stamps(balance, stamp_rate, stamps_supplied, contract=contract, function=func, amount=amount)

    # Check if contract name is valid
    name = transaction['payload']['kwargs'].get('name')
    contract_name_is_valid(contract, func, name)

