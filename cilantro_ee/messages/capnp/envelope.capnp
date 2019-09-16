@0x93eca3fe49376df5;

# can adopt this for SignedMessage ??
# need signature, VK, timestamp, sender ?? - kinda merge of Seal and MessageMeta ??
struct Seal {
    signature @0: Data;
    verifyingKey @1: Data;
}

struct MessageMeta {
    type @0 :UInt16;
    uuid @1: UInt32;
    timestamp @2: Text;
    sender @3: Text;
}

struct Envelope {
    seal @0: Seal;
    meta @1: MessageMeta;
    message @2: Data;
}


struct Message {
    payload @0: Data;
    signature @1: Data;
    verifyingKey @2: Data;
    proof @3: Data;
}
