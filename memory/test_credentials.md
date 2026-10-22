# Test Credentials
# Agent writes here when creating/modifying auth credentials (admin accounts, test users).
# Testing agent reads this before auth tests. Fork/continuation agents read on startup.

## rpsahnni.dev Portfolio
No login / auth in this app — it is a public portfolio site.

- Owner email (receives contact-form alerts): rpsahnni@gmail.com
- Contact endpoint: POST /api/contact  {name, email, message}
  - rate limit: 5 submissions / 10 min per IP
  - test visitor address used during verification: delivered@resend.dev
- Enquiries are stored in MongoDB collection: enquiries
