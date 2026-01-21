# PDS Netra Dashboard (Next.js 14)

A clean, PoC-ready admin dashboard for GSCSCL officials.

## Local run (Mac)

1) Copy env

```bash
cp env.example .env.local
```

2) Install & start

```bash
npm install
npm run dev
```

Open:
- http://localhost:3000

## Notes
- Login stores JWT in `localStorage` (PoC-friendly). For production, switch to HttpOnly cookies.
- The dashboard expects backend APIs under `/api/v1/...` at `NEXT_PUBLIC_API_BASE_URL`.
