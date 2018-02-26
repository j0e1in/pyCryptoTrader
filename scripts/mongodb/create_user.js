use admin

// Root
db.createUser({
  user: "admin",
  pwd: "vv112358",
  roles: [
    { role: "dbAdminAnyDatabase", db: "admin" },
    { role: "userAdminAnyDatabase", db: "admin" },
    { role: "readWriteAnyDatabase", db: "admin" }
  ]
})

db.createUser({
  user: "ex",
  pwd: "vv112358",
  roles: [{ role: "readWriteAnyDatabase", db: "admin" }]
})
