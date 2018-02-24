use exchange

db.createUser({
  user: "admin",
  pwd: "vv112358",
  roles: [{ role: "clusterAdmin", db: "admin" },
          { role: "readAnyDatabase", db: "admin" },
          "readWrite"]
})

