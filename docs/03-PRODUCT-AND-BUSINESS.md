# LogicBuilder — Product & Business Notes

Companion to [01-LOW-LEVEL-DESIGN.md](01-LOW-LEVEL-DESIGN.md) and [02-HIGH-LEVEL-DESIGN.md](02-HIGH-LEVEL-DESIGN.md). Status: v0.2 (local MVP, business groundwork in place).

## 1. Product thesis

**Logic building is a skill, not a topic.** It is built by many small, varied, feedback-rich repetitions (like learning an instrument), not by reading explanations or by three-step tutorials. Most platforms either teach syntax or throw interview problems at people who have no mental model of how code runs.

LogicBuilder's loop for every concept: **See** (watch code execute) → **Predict** (guess what happens) → **Fix** (find the bug) → **Build** (write it) → **Review** (spaced repetition). Every practice problem is wrapped in **Understand → Examples → Plan → Code → Test → Improve**, with a written plan step.

### Exercise types (all graded server-side; the truth is computed by really running code)
| Type | Skill trained |
|---|---|
| Visualize + Predict mode | Mental model of execution |
| Predict the output | Reading code accurately |
| Trace table | Following state through loops |
| Fill the blank | Syntax in context, low pressure |
| Put in order (Parsons) | Sequencing and structure without typing |
| Find the bug | Debugging, the most under-taught skill |
| Practice problems + hint ladder + Plan box | Decomposition and complete solutions |
| Skill map + review queue | Knowing what's weak; remembering it |
| AI tutor (Qwen/Gemma/DeepSeek/Kimi) | Socratic help, sees the learner's code and plan |

## 2. Who pays

| Segment | Pain | Offer |
|---|---|---|
| Self-learners / career switchers (B2C) | Tutorials don't build problem-solving | Free levels 0–4, **Pro** for Core DSA + patterns + AI tutor quota |
| Students (school/college) | Syntax-first teaching, no feedback | Student pricing, regional pricing (e.g. INR) |
| Schools, bootcamps, colleges (B2B) | Can't see who is stuck where | Classroom licence: roster, assignments, the admin analytics view |
| Interview-prep | Pattern gaps | Timed sets, mock rounds (later) |

## 3. Monetisation design (already in the code)
- **Plans:** `free` / `pro` stored per learner; lessons carry `premium` flags; the server enforces them when `LB_PAYWALL=1` (returns HTTP 402). Content answers never reach the browser, so the paywall can't be bypassed by reading the page.
- **Today:** the "Upgrade" button is a local demo. **Production:** checkout (Stripe / Razorpay) → webhook sets `plan`.
- **AI cost control:** local models (Ollama) are free to run; hosted models cost per token, so production needs a per-learner daily quota, a cheap default model, and caching of common explanations.
- **Learning-effect pricing guardrail:** keep the first lessons of every level free so people reach the "I get it" moment before paying.

## 4. Metrics to watch (events are already logged to `data/events.jsonl`)
Activation (finish lesson 1 in first session), D1/D7/D30 retention, exercises per session, **first-try accuracy per exercise** (hardest exercises list in `#/admin` = content to fix), hint usage vs solve rate, review-queue adherence, free→Pro conversion, AI questions per learner (cost driver).

## 5. What exists vs. what a real launch needs

| Area | v0.2 (now) | Needed for production |
|---|---|---|
| Learners | Multiple local profiles, no passwords | Auth (email/OAuth), sessions, account recovery, minors' consent (COPPA/GDPR-K) |
| Data | JSON files per learner | PostgreSQL (repository interface already isolated in `app/store.py`) |
| Code execution | Local subprocess, time/CPU/memory caps | Isolated judge workers (containers, no network, seccomp), queue, rate limits |
| Payments | Demo switch | Checkout + webhooks + invoices + refunds |
| Content | Python files, selftest lints them (every reference solution must pass) | Authoring UI or content repo + CI, review workflow, versioning, ~200 problems, 60+ lessons |
| Analytics | Event log + admin page | Warehouse/dashboard, privacy-safe retention policy |
| Admin | Open local page | Role-based auth, audit log |
| Frontend | Vanilla JS | React/TS per the LLD when the team grows; PWA/mobile |
| Languages | Python, JavaScript, TypeScript, Java, C++, Go, C# (run locally via installed toolchains) | Containerised judge images per language (the `langs.judge()` seam), then Kotlin, Rust, Swift, C. Adding a language = one class in `app/langs.py` + cheat-sheet entries |
| Compliance | n/a | Privacy policy, ToS, cookie consent, content licensing (write original content; do not copy other platforms' problems) |

## 6. Risks
- **Content is the moat and the cost.** Mitigation: content-as-data + selftest; invest in quality of explanation and exercises, not feature count.
- **AI answers that hand over solutions** hurt learning and the brand. Mitigation: the tutor prompt is Socratic and hides solutions; track with sampled review.
- **Execution security** is the largest technical risk at public scale (see HLD §11).
- **Open-model quality varies** (tiny local models explain badly). Mitigation: recommended-model list, a fallback to hosted models for Pro.

## 7. Suggested next 90 days
1. **Weeks 1–3:** grow content to Level 0–4 complete (~40 lessons, 60 problems); run 5–10 real beginners and watch where they stall; fix the "hardest exercises".
2. **Weeks 4–6:** auth + Postgres + deploy (single small VPS); judge container; plan/paywall wired to a payment provider in test mode.
3. **Weeks 7–9:** waitlist/landing page, public beta with free levels, AI quota system, JavaScript support.
4. **Weeks 10–13:** Pro launch, first B2B pilots (one school/bootcamp) using classroom view; iterate on retention.
