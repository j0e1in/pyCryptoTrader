use exchange

coll = db.getCollectionNames()

// Rename ohlcv fields
for (i = 0; i < coll.length; i++) {
  if(coll[i].includes('_ohlcv_')) {
    db.getCollection(coll[i]).updateMany({}, {$rename: {"low": "_close"}})
    db.getCollection(coll[i]).updateMany({}, {$rename: {"high": "low"}})
    db.getCollection(coll[i]).updateMany({}, {$rename: {"close": "high"}})
    db.getCollection(coll[i]).updateMany({}, {$rename: {"_close": "close"}})
  }
}