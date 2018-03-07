use exchange

coll = db.getCollectionNames()

tfs_to_drop = [
  '1m',
  '5m',
  '15m',
  '30m',
  '1h',
  '2h',
  '3h',
  '4h',
  '5h',
  '6h',
  '7h',
  '8h',
  '9h',
  '10h',
  '11h',
  '12h',
  '15h',
  '18h',
  '1d',
]

// Rename ohlcv fields
for (i = 0; i < coll.length; i++) {
  if(coll[i].includes('_ohlcv_')) {
    tf = coll[i].split('_').slice(-1)[0]
    if (tfs_to_drop.includes(tf)) {
      db.getCollection(coll[i]).drop()
    }
  }
}