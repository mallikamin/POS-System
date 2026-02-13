-- PostgreSQL initialization script for POS System
-- This runs automatically when the postgres container is created for the first time.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
