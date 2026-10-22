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
- Projects showcase: 6 projects, bento grid (3/3, 2/4, 4/2 spans), category filters with animated layout
- Tech stack: 6 groups, 39 technologies
- AI automation: interactive n8n flow stepper (auto-cycling) + 4 use cases
- Services: 4 editorial rows with hover arrows
- Contact: working form → /api/contact → email alert to owner + confirmation to visitor (verified, emailed:true), quick contact rows, sonner toasts
- Navbar with scroll progress bar, mobile menu; footer with socials + back-to-top
- Responsive verified at 375 / 768 / 1366
- Git repo initialised at /app with commit; .env excluded via .gitignore

## Backlog
- P0: none blocking
- P1: per-project case study pages / modal with screenshots and GitHub/live links (projects currently have no external links)
- P1: real photo/avatar of Ram for an About section
- P2: blog / notes section, testimonials, analytics dashboard for enquiries, downloadable resume PDF
- Next tasks: collect project repo/demo links from user; push to user's GitHub (needs his repo access); deploy
