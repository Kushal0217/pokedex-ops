-- Pokédex Ops schema.
--
-- Reference tables (pokemon, types, moves, ...) hold real PokeAPI data.
-- Workload tables (trainers, teams, battles, encounters) are synthetic and big,
-- so that query plans and index choices actually matter.
--
-- Workload tables deliberately carry ONLY primary keys: no foreign-key indexes,
-- no secondary indexes. Finding and fixing that is the agent's job.

DROP TABLE IF EXISTS ops_audit_log, encounters, battles, team_members, teams, trainers,
    pokemon_moves, pokemon_abilities, pokemon_types, moves, abilities, pokemon, types CASCADE;

-- ---------------------------------------------------------------- reference
CREATE TABLE types (
    id    int PRIMARY KEY,
    name  text NOT NULL UNIQUE
);

CREATE TABLE pokemon (
    id              int PRIMARY KEY,
    name            text NOT NULL UNIQUE,
    generation      int  NOT NULL,
    height_dm       int  NOT NULL,
    weight_hg       int  NOT NULL,
    base_experience int,
    hp              int  NOT NULL,
    attack          int  NOT NULL,
    defense         int  NOT NULL,
    sp_attack       int  NOT NULL,
    sp_defense      int  NOT NULL,
    speed           int  NOT NULL,
    is_legendary    boolean NOT NULL DEFAULT false,
    is_mythical     boolean NOT NULL DEFAULT false
);

CREATE TABLE pokemon_types (
    pokemon_id int NOT NULL REFERENCES pokemon(id),
    type_id    int NOT NULL REFERENCES types(id),
    slot       int NOT NULL,
    PRIMARY KEY (pokemon_id, slot)
);

CREATE TABLE abilities (
    id    int PRIMARY KEY,
    name  text NOT NULL UNIQUE
);

CREATE TABLE pokemon_abilities (
    pokemon_id int NOT NULL REFERENCES pokemon(id),
    ability_id int NOT NULL REFERENCES abilities(id),
    is_hidden  boolean NOT NULL,
    slot       int NOT NULL,
    PRIMARY KEY (pokemon_id, slot)
);

CREATE TABLE moves (
    id            int PRIMARY KEY,
    name          text NOT NULL UNIQUE,
    type_id       int REFERENCES types(id),
    damage_class  text,
    power         int,
    accuracy      int,
    pp            int,
    generation    int
);

CREATE TABLE pokemon_moves (
    pokemon_id    int  NOT NULL REFERENCES pokemon(id),
    move_id       int  NOT NULL REFERENCES moves(id),
    learn_method  text NOT NULL,
    level_learned int  NOT NULL,
    PRIMARY KEY (pokemon_id, move_id, learn_method)
);

-- ---------------------------------------------------------------- workload
CREATE TABLE trainers (
    id          bigint PRIMARY KEY,
    username    text        NOT NULL,
    region      text        NOT NULL,
    created_at  timestamptz NOT NULL,
    is_banned   boolean     NOT NULL DEFAULT false
);

CREATE TABLE teams (
    id          bigint PRIMARY KEY,
    trainer_id  bigint      NOT NULL,
    name        text        NOT NULL,
    format      text        NOT NULL,      -- singles | doubles | little-cup | monotype
    created_at  timestamptz NOT NULL,
    is_public   boolean     NOT NULL
);

CREATE TABLE team_members (
    team_id     bigint NOT NULL,
    slot        int    NOT NULL,
    pokemon_id  int    NOT NULL,
    level       int    NOT NULL,
    nickname    text,
    PRIMARY KEY (team_id, slot)
);

CREATE TABLE battles (
    id              bigint PRIMARY KEY,
    played_at       timestamptz NOT NULL,
    format          text        NOT NULL,
    region          text        NOT NULL,
    winner_team_id  bigint      NOT NULL,
    loser_team_id   bigint      NOT NULL,
    turns           int         NOT NULL,
    is_ranked       boolean     NOT NULL
);

CREATE TABLE encounters (
    id              bigint PRIMARY KEY,
    trainer_id      bigint      NOT NULL,
    pokemon_id      int         NOT NULL,
    location        text        NOT NULL,
    encountered_at  timestamptz NOT NULL,
    level           int         NOT NULL,
    is_shiny        boolean     NOT NULL,
    caught          boolean     NOT NULL
);

-- What staging ran. Fixture data for the incident-response tasks.
CREATE TABLE ops_audit_log (
    id            bigserial PRIMARY KEY,
    occurred_at   timestamptz NOT NULL,
    db_user       text        NOT NULL,
    environment   text        NOT NULL,
    statement     text        NOT NULL,
    rows_affected bigint
);
