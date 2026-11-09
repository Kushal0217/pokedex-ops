-- Runs once, as the superuser, when the data volume is first created.

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS hypopg;

-- The agent's read path. Least privilege: SELECT on the data, read access to
-- stats views, and every transaction read-only by default. The MCP server also
-- opens its own READ ONLY transactions; this is the second lock on the door.
CREATE ROLE pokedex_agent LOGIN PASSWORD 'agent';
ALTER ROLE pokedex_agent SET default_transaction_read_only = on;
ALTER ROLE pokedex_agent SET statement_timeout = '30s';
GRANT pg_read_all_stats TO pokedex_agent;
GRANT CONNECT ON DATABASE pokedex TO pokedex_agent;
GRANT USAGE ON SCHEMA public TO pokedex_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pokedex_agent;

-- The one write path: apply_index connects as the table owner, because only
-- the owner may CREATE INDEX. The server only ever sends it CREATE INDEX.
CREATE ROLE pokedex_dba LOGIN PASSWORD 'dba';
GRANT ALL ON SCHEMA public TO pokedex_dba;
GRANT CONNECT ON DATABASE pokedex TO pokedex_dba;
GRANT pg_read_all_stats TO pokedex_dba;
ALTER DEFAULT PRIVILEGES FOR ROLE pokedex_dba IN SCHEMA public GRANT SELECT ON TABLES TO pokedex_agent;
