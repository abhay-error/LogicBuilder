# Security

## Current scope: local use only

LogicBuilder v0.x is designed to run on your own computer and to listen on `127.0.0.1` only.

- **Learner code runs with your user rights.** Python code runs in a separate process with a time limit (plus CPU and memory limits on Linux/macOS); JavaScript, TypeScript, Java, C++, Go and C# run as normal programs after compiling. This is the same as running the code yourself. It is **not** a sandbox against hostile code.
- **Do not bind the server to a public interface or put it behind a public URL** in this form. There is no authentication; the admin page and learner profiles are open.
- **AI keys** are stored in `data/ai_config.json` (git-ignored). Never commit that file.
- Hidden test cases and exercise answers stay on the server and are not sent to the browser.

## Before a public deployment

See `docs/02-HIGH-LEVEL-DESIGN.md` section 11 and `docs/03-PRODUCT-AND-BUSINESS.md` section 5: authentication, a database, containerised code execution (no network, read-only filesystem, resource limits), rate limiting, and a locked-down admin area.

## Reporting a vulnerability

Please report security problems privately to the repository owner rather than opening a public issue.
