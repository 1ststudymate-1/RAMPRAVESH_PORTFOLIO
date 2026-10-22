# Auth Testing Playbook — rpsahnni.dev

Step 1: MongoDB Verification
```
mongosh
use test_database
db.users.find({role: "admin"}).pretty()
db.users.findOne({role: "admin"}, {password_hash: 1})
```
Verify: bcrypt hash starts with `$2b$`; unique index on users.email; index on login_attempts.identifier.

Step 2: API Testing
```
curl -c cookies.txt -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"ADMIN_EMAIL","password":"ADMIN_PASSWORD"}'
cat cookies.txt
curl -b cookies.txt $API/api/auth/me
```
Login returns {"token", "user"} and sets access_token cookie. /me returns admin user.

Step 3: Admin CRUD
```
TOKEN=$(curl -s -X POST $API/api/auth/login ... | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s $API/api/admin/projects -H "Authorization: Bearer $TOKEN"
```
Unauthenticated admin calls must return 401.
