# struct TransactionBatch {
#     transactions @0 :List(NewTransaction);
#     timestamp @1: Float64;
#     signature @2: Data;
#     sender @3: Data;
#     inputHash @4: Text;  # hash of transactions + timestamp
# }

