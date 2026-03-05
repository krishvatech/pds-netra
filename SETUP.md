# Digital Netra Setup Guide

## Prerequisites
- PostgreSQL running on `127.0.0.1:55432`
- PostgreSQL user: `digitalnetra`
- Node.js and npm installed
- Python and Poetry installed

## 1. Create Database (One-Time)

```bash
psql -h 127.0.0.1 -p 55432 -U digitalnetra -d digitalnetra \
  -c 'CREATE DATABASE "digital-netra" OWNER digitalnetra;'
```

## 2. Backend Setup & Run

Navigate to the backend directory and install dependencies:

```bash
cd /home/yashvi-radadiya/pds-netras/pds-netra/digital-netra-backend
poetry install
```

Run database migrations:

```bash
poetry run alembic upgrade head
```

Start the backend server:

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

The backend will be available at `http://localhost:8002`

## 3. Frontend Setup & Run

Navigate to the frontend directory and install dependencies:

```bash
cd /home/yashvi-radadiya/pds-netras/pds-netra/digital-netra-dashboard
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend will be available at the address shown in your terminal (typically `http://localhost:3000` or `http://localhost:5173`)

## 4. Grant Admin Access (Optional)

To make a user an admin, run the following SQL query:

```sql
UPDATE app_user SET is_admin = TRUE WHERE email = 'user@example.com';
```

Replace `user@example.com` with the actual user email.

## Quick Start Script

To run all services at once, open separate terminals and execute:

**Terminal 1 - Backend:**
```bash
cd /home/yashvi-radadiya/pds-netras/pds-netra/digital-netra-backend
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

**Terminal 2 - Frontend:**
```bash
cd /home/yashvi-radadiya/pds-netras/pds-netra/digital-netra-dashboard
npm run dev
```
