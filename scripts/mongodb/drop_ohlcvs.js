use exchange

coll = db.getCollectionNames()

tfs_to_drop = [
  '2h',
  '4h',
  '5h',
  '7h',
  '8h',
  '9h',
  '10h',
  '11h',
  '15h',
  '18h',
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