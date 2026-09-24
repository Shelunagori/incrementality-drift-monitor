-- Runs once on first container start: test database + pgvector in both DBs.
CREATE DATABASE idm_test OWNER idm;
CREATE EXTENSION IF NOT EXISTS vector;
\connect idm_test
CREATE EXTENSION IF NOT EXISTS vector;
