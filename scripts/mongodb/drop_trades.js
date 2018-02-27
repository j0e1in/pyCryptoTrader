use exchange

coll = db.getCollectionNames()

// Rename ohlcv fields
for (i = 0; i < coll.length; i++) {
  if(coll[i].includes('_trades_')) {
    db.getCollection(coll[i]).drop()
  }
}