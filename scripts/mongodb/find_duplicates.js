coll = db.getCollectionNames()

for (i = 0; i < coll.length; i++) {
  if(coll[i].includes('_ohlcv_')) {
    collection = db.getCollection(coll[i])

    // Find duplicates
    collection.aggregate([
        { "$group": {
            "_id": { "timestamp": "$timestamp" },
            "dups": { "$push": "$_id" },
            "count": { "$sum": 1 }
        }},
        { "$match": { "count": { "$gt": 1 } }}
    ])
  }
}
