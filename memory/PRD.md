# PRD — rpsahnni.dev Portfolio

## Original problem statement
"is file ko achhe se analyse karke portfolio website bana do jo unique ke sath sath professional ho, sath hi maine jitne project banaya hai unsabhi ko showcase kar saku, ise aap complete banakar do mujhe" — User uploaded an existing React portfolio zip (Ram Pravesh Sahni, freelance developer, Deoghar, Jharkhand) and asked for a unique, professional, complete rebuild showcasing all his projects.

## User choices (confirmed)
- Language: English
- Contact: form + email alert (Emergent managed Resend) to rpsahnni@gmail.com
- Socials: github.com/rpsahnni-creator · linkedin.com/in/rp-sahnni
- Look & feel: dark + bold accent
- Keep committing to git (local commits done; push needs his GitHub credentials)

## User personas
- Potential freelance clients (startups, SMEs) evaluating his work
- Recruiters reviewing full-stack / mobile / AI automation capability
- Ram himself, sending the link as his professional identity

## Architecture
- Frontend: React 19 + Tailwind + framer-motion + lenis (smooth scroll), Syne/Plus Jakarta Sans/JetBrains Mono, custom RP monogram SVG (also favicon)
- Backend: FastAPI, POST /api/contact (validation, IP rate limit 5/10min, MongoDB store, owner alert + visitor confirmation emails via Emergent managed email proxy with G2/G3 guardrail gate)
- DB: MongoDB (enquiries collection)
- Design system: /app/design_guidelines.json (dark #070A0F, emerald #10B981 accent, amber #F59E0B secondary)

## Implemented (2026-07-22)
- Signature intro overlay + kinetic hero with masked line-by-line reveal, role rotator, parallax code card, dot-grid + glow
- Editorial marquee ticker
- About section: bio, stats strip (6 projects / 39 tech / 4 disciplines / 24-7), identity card with socials
- Projects showcase: 6 projects, bento grid, category filters with animated layout; every card opens a case-study modal (features, outcome, tech pills, GitHub link — currently the profile URL as a placeholder, "start a similar project" CTA)
- Tech stack: 6 groups, 39 technologies
- AI automation: interactive n8n flow stepper (auto-cycling) + 4 use cases
- Services: 4 editorial rows with hover arrows
- Contact: working form → /api/contact → email alert to owner + confirmation to visitor (verified, emailed:true), quick contact rows, sonner toasts
- Navbar with scroll progress bar, mobile menu; footer with socials + back-to-top
- Responsive verified at 375 / 768 / 1366; modal open/close + About nav verified
- Git repo at /app with commits; .env excluded via .gitignore
- Dark + light theme toggle (navbar sun/moon button, persisted in localStorage, full CSS-variable color system; terminal code card stays dark in both themes deliberately)
- Visual project showcase: featured spotlight card (Billing & Invoice API, full-width with image) + image headers with ghost index numbers on all cards and in case-study modals (curated images from design_guidelines)
- Testimonials: auto-rotating editorial quote carousel (4 SAMPLE quotes — user must replace with real client words), prev/next + dots, star row, works in both themes
- Resume: one-page PDF generated via /app/scripts/make_resume.py (reportlab), served at /Ram-Pravesh-Sahni-Resume.pdf, download buttons in Hero (hero-resume-button) and About card (about-resume-button)
- Admin panel at /admin: JWT login (bcrypt, 12h token, brute-force lockout 5 tries/15 min), tabs for Projects (add/edit/delete, image upload or URL, featured toggle), Tech Stack, Testimonials, Resume PDF upload (stored in MongoDB, served at /api/resume), Enquiries inbox (contact-form messages), Password (change-password endpoint; seed is seed-only-if-missing so in-app changes persist)
- Code pushed to GitHub: github.com/1ststudymate-1/RAMPRAVESH_PORTFOLIO (main, latest commit ae97589, 2026-07-22)
- Enquiry reply: POST /api/admin/enquiries/{id}/reply (recipient from DB, server template) + Reply UI in Enquiries tab with REPLIED badge
- Analytics: POST /api/track (session-based, no personal data) + GET /api/admin/analytics (7-day views, unique visitors, enquiries, top referrers) + Analytics tab (default admin view)
- Admin entry points on public site: lock icon in navbar (desktop + mobile menu) and "Admin" link in footer, both → /admin
- Site content now DB-driven: GET /api/content serves projects/skills/testimonials from MongoDB (seeded from defaults on first start); frontend falls back to static data.js if API fails

## Backlog
- P0: none blocking
- P1: replace placeholder GitHub profile links with per-project repo / live demo URLs (user must share them)
- P1: real photo of Ram in the About section (user upload needed)
- P2: blog / notes section, testimonials, enquiries admin view, downloadable resume PDF
- Next tasks: collect per-project repo/demo links + portrait photo; connect user's GitHub remote for push; deploy
