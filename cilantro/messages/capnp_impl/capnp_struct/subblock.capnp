@0xab5e7866e64c6d4d;

using T = import "transaction.capnp";

# SubBlock is intended to be nested inside of BlockData, and never really used on its own
# todo - remove hash from MerkleProof - it is same as MerkleRoot at higher level
#      - remove inputHash from SubBlock
#      - include SubBlock as part of SubBlockContender with additional fields: prevBlockHash and inputHash

struct MerkleProof {
    hash @0 :Data;
    signer @1: Data;
    signature @2: Data;
}

struct Signature {
    signer @0: Data;
    signature @1 :Data;
}

struct MerkleTree {
    leaves @0 :List(Data);
    signature @1 :Data;
}

struct SubBlock {
    inputHash @0: Text;
    transactions @1: List(T.TransactionData);
    merkleLeaves @2: List(Data);
    signatures @3: List(Signature);
    subBlockNum @4: UInt8;
    prevBlockHash @5: Text;
}

struct SubBlockContender {
    inputHash @0 :Text;
    transactions @1: List(T.TransactionData);
    merkleTree @2 :MerkleTree;
    signer @3 :Data;
    subBlockNum @4: UInt8;
    prevBlockHash @5: Text;
}

struct SubBlockContenders {
    contenders @0 :List(SubBlockContender);
}