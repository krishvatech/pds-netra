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
- Login stores the auth token in an `HttpOnly` cookie; client code does not read JWTs directly.
- The dashboard expects backend APIs under `/api/v1/...` at `NEXT_PUBLIC_API_BASE_URL`.
