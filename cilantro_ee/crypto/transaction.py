import time

from cilantro_ee.crypto.canonical import format_dictionary
from cilantro_ee.crypto.wallet import sign
from cilantro_ee.formatting import check_format, rules
from contracting.db.encoder import encode
from contracting.db.driver import ContractDriver
from cilantro_ee.crypto import wallet


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
}


def check_tx_formatting(tx: dict, expected_processor: str):
    if not check_format(tx, rules.TRANSACTION_RULES):
        return TransactionFormattingError

    if not wallet.verify(
            bytes.fromhex(tx['payload']['sender']),
            encode(tx['payload']).encode(),
            bytes.fromhex(tx['metadata']['signature'])
    ):
        return TransactionSignatureInvalid

    if tx['payload']['processor'] != expected_processor:
        return TransactionProcessorInvalid


def get_nonces(sender, processor, driver: ContractDriver):
    nonce = driver.get_nonce(
        processor=bytes.fromhex(processor),
        sender=bytes.fromhex(sender)
    )
    if nonce is None:
        nonce = 0

    pending_nonce = driver.get_pending_nonce(
        processor=bytes.fromhex(processor),
        sender=bytes.fromhex(sender)
    )
    if pending_nonce is None:
        pending_nonce = 0

    return nonce, pending_nonce


def get_new_pending_nonce(tx_nonce, nonce, pending_nonce, strict=True, tx_per_block=15):
    # Attempt to get the current block's pending nonce
    if tx_nonce - nonce > tx_per_block or pending_nonce - nonce >= tx_per_block:
        raise TransactionTooManyPendingException

    if strict:
        if tx_nonce != pending_nonce:
            raise TransactionNonceInvalid
        pending_nonce += 1

    else:
        if tx_nonce < pending_nonce:
            raise TransactionNonceInvalid
        pending_nonce = tx_nonce + 1

    return pending_nonce


def has_enough_stamps(balance, stamp_per_balance, stamps_supplied, contract=None, function=None, amount=0):
    if balance * stamp_per_balance < stamps_supplied:
        raise TransactionSenderTooFewStamps

    # Prevent people from sending their entire balances for free by checking if that is what they are doing.
    if contract == 'currency' and function == 'transfer':

        # If you have less than 2 transactions worth of tau after trying to send your amount, fail.
        if ((balance - amount) * stamp_per_balance) / 6000 < 2:
            raise TransactionSenderTooFewStamps


def contract_name_is_valid(contract, function, name):
    if contract == 'submission' and function == 'submit_contract' and not contract_name_is_formatted(name):
        raise TransactionContractNameInvalid


def build_transaction(wallet, contract: str, function: str, kwargs: dict, nonce: int, processor: str, stamps: int):
    payload = {
        'contract': contract,
        'function': function,
        'kwargs': kwargs,
        'nonce': nonce,
        'processor': processor,
        'sender': wallet.verifying_key().hex(),
        'stamps_supplied': stamps,
    }

    assert check_format(payload, rules.TRANSACTION_PAYLOAD_RULES), 'Invalid payload provided!'

    signature = sign(wallet.signing_key(), encode(payload).encode())

    metadata = {
        'signature': signature.hex(),
        'timestamp': int(round(time.time() * 1000))
    }

    tx = {
        'payload': payload,
        'metadata': metadata
    }

    return encode(format_dictionary(tx))