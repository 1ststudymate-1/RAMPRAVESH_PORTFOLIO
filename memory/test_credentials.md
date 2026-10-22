# Test Credentials
# Agent writes here when creating/modifying auth credentials (admin accounts, test users).
# Testing agent reads this before auth tests. Fork/continuation agents read on startup.

## rpsahnni.dev Portfolio

### Admin panel (/admin)
- Email: rpsahnni@gmail.com
- Password: Rpsahnni#2026  (TEST credential — seeded only when admin is missing; password can be changed in admin panel → Password tab, and the changed password persists across restarts)
- Role: admin
- Auth endpoints: POST /api/auth/login, GET /api/auth/me, POST /api/auth/logout
- Admin APIs: /api/admin/projects|skills|testimonials|enquiries, POST /api/admin/files, POST /api/admin/resume

### Contact form
- Owner email (receives alerts): rpsahnni@gmail.com
- POST /api/contact {name, email, message} — rate limit 5 / 10 min per IP
- Test visitor address used during verification: delivered@resend.dev
- Enquiries stored in MongoDB collection: enquiries (also visible in admin panel)
