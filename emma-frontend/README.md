# Emma Frontend (Quick Start)

A tiny React + Vite app to paste a transcript, call the backend `/analyze` API, and view the extracted incident form, evidence, and draft email.

---

## Prerequisites

- **Node.js 18+** (`node -v`)
- **npm** (`npm -v`)
- Running backend (default at `http://127.0.0.1:8000`)

---

## Setup & Run (dev)

```bash
# 1) go to the frontend
cd emma-frontend

# 2) install deps
npm install

# 3) (optional) point to your backend if not on 127.0.0.1:8000
# macOS/Linux:
export VITE_API_URL=http://127.0.0.1:8000
# Windows PowerShell:
# $env:VITE_API_URL="http://127.0.0.1:8000"

# 4) start the dev server
npm run dev
