use exchange

coll = db.getCollectionNames()

// Create unique timestamp index for ohlcvs
for (i = 0; i < coll.length; i++) {
  if(coll[i].includes('_ohlcv_')) {
    db.getCollection(coll[i]).createIndex({'timestamp':1}, {'unique': true})
  }
}


// Create timestamp index for trades
for (i = 0; i < coll.length; i++) {
  if(coll[i].includes('_trades_')) {
    db.getCollection(coll[i]).createIndex({'timestamp':1})
  }
}
