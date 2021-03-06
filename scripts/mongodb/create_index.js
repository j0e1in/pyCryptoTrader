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
        collection.remove({ "_id": {"$in": doc.dups } });
    })

    // Create unique index
    collection.createIndex({"timestamp": 1},{unique:true})
  }
}


// Create unique id index and timestamp index for trades
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
            { "$match": { "count": { "$gt": 1 } } }
        ],

        { "allowDiskUse": true }

    // Remove duplicates
    ).forEach(function(doc) {
        doc.dups.shift();
        collection.remove({ "_id": {"$in": doc.dups } });
    })

    // Create unique index
    collection.createIndex({"id": 1},{unique:true})
    collection.createIndex({"timestamp": 1})
  }
}


use trade

coll = db.getCollectionNames()

// Create unique id index and timestamp index for trades
for (i = 0; i < coll.length; i++) {
    if (coll[i].includes('_trades')) {
        collection = db.getCollection(coll[i])

        // Find duplicates
        collection.aggregate(
            [
                { "$group": {
                        "_id": { "id": "$id" },
                        "dups": { "$push": "$_id" },
                        "count": { "$sum": 1 }
                }},
                { "$match": { "count": { "$gt": 1 } } }
            ],

            { "allowDiskUse": true }

            // Remove duplicates
        ).forEach(function (doc) {
            doc.dups.shift();
            collection.remove({ "_id": { "$in": doc.dups } });
        })

        // Create unique index
        collection.createIndex({ "id": 1 }, { unique: true })
        collection.createIndex({ "timestamp": 1 })
    }
}

use api

// Create unique id index and timestamp index for trades

collection = db.getCollection('authy_account')

// Find duplicates
collection.aggregate(
    [
        {
            "$group": {
                "_id": { "uid": "$uid" },
                "dups": { "$push": "$_id" },
                "count": { "$sum": 1 }
            }
        },
        { "$match": { "count": { "$gt": 1 } } }
    ],

    { "allowDiskUse": true }

    // Remove duplicates
).forEach(function (doc) {
    doc.dups.shift();
    collection.remove({ "_id": { "$in": doc.dups } });
})

// Create unique index
collection.createIndex({ "uid": 1 }, { unique: true })


use analysis

collection = db.getCollection('param_set_meta')
collection.createIndex({ "name": 1 }, { unique: true })

collection = db.getCollection('param_optimization')
collection.createIndex({ "PL(%)": 1 }, { unique: false })
