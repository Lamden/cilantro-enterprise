from decimal import Decimal
from cilantro_ee.protocol import wallet
from cilantro_ee.protocol.pow import SHA3POW
from cilantro_ee.messages import capnp as schemas
import time
import os
import capnp

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

NUMERIC_TYPES = {int, Decimal}
VALUE_TYPE_MAP = {
    str: 'text',
    bytes: 'data',
    bool: 'bool'
}


class ContractTransaction:
    def __init__(self, sender, stamps: int, contract: str, function: str, nonce: str, kwargs: dict):
        # Stores variables in self for convenience
        self.sender = sender
        self.stamps = stamps
        self.contract = contract
        self.function = function
        self.nonce = nonce
        self.kwargs = kwargs

        # Serializes all that it can on init
        self.struct = transaction_capnp.ContractTransaction.new_message()
        self.payload = transaction_capnp.ContractPayload.new_message()

        self.payload.sender = self.sender
        self.payload.stampsSupplied = self.stamps
        self.payload.contractName = self.contract
        self.payload.functionName = self.function
        self.payload.nonce = self.nonce

        # Create a list of entries in Capnproto
        self.payload.kwargs.init('entries', len(self.kwargs))

        # Enumerate through the Python dictionary and make sure to type cast when needed for Capnproto
        for i, key in enumerate(self.kwargs):
            self.payload.kwargs.entries[i].key = key
            value, t = self.kwargs[key], type(self.kwargs[key])

            # Represent numeric types as strings so we do not lose any precision due to floating point
            if t in NUMERIC_TYPES:
                self.payload.kwargs.entries[i].value.fixedPoint = str(value)

            # This should be streamlined with explicit encodings for different types
            # For example, 32 byte strings -> UInt32
            else:
                assert t is not float, "Float types not allowed in kwargs. Used python's decimal.Decimal class instead"
                assert t in VALUE_TYPE_MAP, "value type {} with value {} not recognized in " \
                                            "types {}".format(t, self.kwargs[key], list(VALUE_TYPE_MAP.keys()))
                setattr(self.payload.kwargs.entries[i].value, VALUE_TYPE_MAP[t], value)

        self.payload_bytes = self.payload.to_bytes_packed()
        self.signature = None
        self.proof = None

        self.proof_generated = False
        self.tx_signed = False

    def sign(self, signing_key):
        # signs the payload binary
        self.signature = wallet.sign(signing_key, self.payload_bytes)
        self.tx_signed = True

    def generate_proof(self):
        self.proof = SHA3POW.find(self.payload_bytes)[0]
        self.proof_generated = True

    def serialize(self):
        if not self.tx_signed:
            return None

        if not self.proof_generated:
            self.generate_proof()

        self.struct.payload = self.payload_bytes
        self.struct.metadata.proof = self.proof
        self.struct.metadata.signature = self.signature
        self.struct.metadata.timestamp = int(time.time())

        return self.struct.to_bytes_packed()


def verify_packed_tx(sender, tx):
    try:
        unpacked = transaction_capnp.ContractTransaction.from_bytes_packed(tx)
        msg = unpacked.payload

        proof = SHA3POW.check(msg, unpacked.metadata.proof.decode())
        sig = bytes.fromhex(unpacked.metadata.signature.decode())

        verified = wallet._verify(sender, msg, sig)
        return verified and proof
    except:
        return False