#!/usr/bin/env python3
"""Test script to verify authorized_users table creation."""

from app.models import Base, AuthorizedUser
from app.core.db import engine
from sqlalchemy import inspect

# Create tables
Base.metadata.create_all(bind=engine)
print("✓ Database tables created successfully")

# Inspect tables
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"✓ Tables: {', '.join(tables)}")

if 'authorized_users' in tables:
    print("✓ authorized_users table exists")
    cols = [c['name'] for c in inspector.get_columns('authorized_users')]
    print(f"✓ Columns: {', '.join(cols)}")
else:
    print("✗ authorized_users table NOT found")
