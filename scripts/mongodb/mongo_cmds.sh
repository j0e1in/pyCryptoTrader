# Dump to an archive
mongodump -d [db] -c [coll] --gzip --archive=[path]

# Restore an archive
mongorestore --gzip --archive=[path]