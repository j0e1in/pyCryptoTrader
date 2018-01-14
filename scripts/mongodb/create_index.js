use exchange

coll = db.getCollectionNames()

// Create unique timestamp index for ohlcvs
for (i = 0; i < coll.length; i++) {
  if(coll[i].includes('_ohlcv_')) {
    collection = db.getCollection(coll[i])

    // Find duplicates
    collection.aggregate(
        [
            { "$group": {
                "_id": { "timestamp": "$timestamp" },
                "dups": { "$push": "$_id" },
                "count": { "$sum": 1 }
            }},
            { "$match": { "count": { "$gt": 1 } }}
        ],

        { "allowDiskUse": true }

    // Remove duplicates
    ).forEach(function(doc) {
        doc.dups.shift();
        collection.remove({ "_id": {"$in": doc.dups }});
    })

    // Create unique index
    collection.createIndex({"timestamp": 1},{unique:true})
  }
}


// Create timestamp index for trades
for (i = 0; i < coll.length; i++) {
  if(coll[i].includes('_trades_')) {
    collection = db.getCollection(coll[i])

    // Find duplicates
    collection.aggregate(
        [
            { "$group": {
                "_id": { "id": "$id" },
                "dups": { "$push": "$_id" },
                "count": { "$sum": 1 }
            }},
            { "$match": { "count": { "$gt": 1 } }}
        ],

        { "allowDiskUse": true }

    // Remove duplicates
    ).forEach(function(doc) {
        doc.dups.shift();
        collection.remove({ "_id": {"$in": doc.dups }});
    })

    // Create unique index
    collection.createIndex({"id": 1},{unique:true})
    collection.createIndex({"timestamp": 1})
  }
}
