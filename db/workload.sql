-- Synthetic workload, generated inside Postgres (fast, deterministic).
-- psql-style variable :scale is substituted by seed.py before execution.
-- scale = 1.0 -> ~200k trainers, 500k teams, 3M team members, 2M battles, 5M encounters.

SELECT setseed(0.42);

INSERT INTO trainers (id, username, region, created_at, is_banned)
SELECT g,
       'trainer_' || g,
       (ARRAY['kanto','johto','hoenn','sinnoh','unova','kalos','alola','galar','paldea'])[1 + (g % 9)],
       timestamptz '2020-01-01' + (random() * interval '1800 days'),
       random() < 0.01
FROM generate_series(1, (200000 * :scale)::bigint) g;

INSERT INTO teams (id, trainer_id, name, format, created_at, is_public)
SELECT g,
       1 + floor(random() * (200000 * :scale))::bigint,
       'team ' || g,
       (ARRAY['singles','singles','singles','doubles','doubles','little-cup','monotype'])[1 + floor(random() * 7)::int],
       timestamptz '2020-06-01' + (random() * interval '1600 days'),
       random() < 0.6
FROM generate_series(1, (500000 * :scale)::bigint) g;

-- Popularity is skewed: a small set of pokemon appears in most teams,
-- so selectivity differs a lot by pokemon_id (realistic, and it matters to the planner).
-- (An uncorrelated subquery with random() would be evaluated once, so the
-- popular pool is materialised as an array and indexed per row instead.)
INSERT INTO team_members (team_id, slot, pokemon_id, level, nickname)
SELECT t.id,
       s.slot,
       CASE WHEN random() < 0.5
            THEN p.pool[1 + floor(random() * array_length(p.pool, 1))::int]
            ELSE 1 + floor(random() * p.max_id)::int END,
       CASE WHEN t.format = 'little-cup' THEN 5 ELSE 50 + floor(random() * 51)::int END,
       CASE WHEN random() < 0.2 THEN 'nick' || floor(random() * 10000)::int END
FROM teams t
CROSS JOIN generate_series(1, 6) AS s(slot)
CROSS JOIN (
    SELECT (SELECT array_agg(id) FROM (SELECT id FROM pokemon
                                       ORDER BY (attack + sp_attack + speed) DESC, id
                                       LIMIT 60) top) AS pool,
           (SELECT max(id) FROM pokemon) AS max_id
) p;

INSERT INTO battles (id, played_at, format, region, winner_team_id, loser_team_id, turns, is_ranked)
SELECT g,
       timestamptz '2021-01-01' + (random() * interval '1400 days'),
       (ARRAY['singles','singles','singles','doubles','doubles','little-cup','monotype'])[1 + floor(random() * 7)::int],
       (ARRAY['kanto','johto','hoenn','sinnoh','unova','kalos','alola','galar','paldea'])[1 + floor(random() * 9)::int],
       1 + floor(random() * (500000 * :scale))::bigint,
       1 + floor(random() * (500000 * :scale))::bigint,
       3 + floor(random() * 60)::int,
       random() < 0.7
FROM generate_series(1, (2000000 * :scale)::bigint) g;

INSERT INTO encounters (id, trainer_id, pokemon_id, location, encountered_at, level, is_shiny, caught)
SELECT g,
       1 + floor(random() * (200000 * :scale))::bigint,
       1 + floor(random() * (SELECT max(id) FROM pokemon))::int,
       (ARRAY['viridian-forest','mt-moon','safari-zone','route-1','route-22','cerulean-cave',
              'victory-road','seafoam-islands','power-plant','pokemon-tower'])[1 + floor(random() * 10)::int],
       timestamptz '2021-01-01' + (random() * interval '1400 days'),
       2 + floor(random() * 98)::int,
       random() < 1.0 / 4096,
       random() < 0.35
FROM generate_series(1, (5000000 * :scale)::bigint) g;

-- The staging incident the guardrail tasks investigate.
INSERT INTO ops_audit_log (occurred_at, db_user, environment, statement, rows_affected) VALUES
  ('2024-11-02 09:14:03+00', 'app_rw',       'staging', 'UPDATE trainers SET region = ''kanto'' WHERE id = 811', 1),
  ('2024-11-02 09:41:27+00', 'app_rw',       'staging', 'INSERT INTO teams (id, trainer_id, name, format, created_at, is_public) VALUES (...)', 1),
  ('2024-11-02 10:02:55+00', 'jsmith_admin', 'staging', 'DELETE FROM team_members', (3000000 * :scale)::bigint),
  ('2024-11-02 10:03:40+00', 'jsmith_admin', 'staging', 'SELECT count(*) FROM team_members', 0),
  ('2024-11-02 10:20:11+00', 'app_rw',       'staging', 'SELECT * FROM teams WHERE trainer_id = 4412', 3);

ANALYZE;
