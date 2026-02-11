"""SQLite DDL for OOD-CP metadata persistence.

Defines the schema for datasets, datafiles, and dataversions tables.
Used by SQLiteMetadataAdapter to ensure tables exist on first access.
"""

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS datasets (
    uuid          TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT NOT NULL DEFAULT '',
    project       TEXT NOT NULL DEFAULT '',
    owner         TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    shared_metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS datafiles (
    uuid          TEXT PRIMARY KEY,
    dataset_uuid  TEXT NOT NULL REFERENCES datasets(uuid),
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    owner         TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE(dataset_uuid, name)
);

CREATE TABLE IF NOT EXISTS dataversions (
    uuid                TEXT PRIMARY KEY,
    datafile_uuid       TEXT NOT NULL REFERENCES datafiles(uuid),
    version_number      INTEGER NOT NULL,
    dvc_hash            TEXT NOT NULL DEFAULT '',
    hash_algorithm      TEXT NOT NULL DEFAULT 'md5',
    storage_uri         TEXT NOT NULL DEFAULT '',
    storage_type        TEXT NOT NULL DEFAULT 'LOCAL',
    status              TEXT NOT NULL DEFAULT 'DRAFT',
    source_version_uuid TEXT REFERENCES dataversions(uuid),
    transformer         TEXT NOT NULL DEFAULT '',
    metadata            TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE(datafile_uuid, version_number)
);

CREATE INDEX IF NOT EXISTS idx_datafiles_dataset
    ON datafiles(dataset_uuid);
CREATE INDEX IF NOT EXISTS idx_dataversions_datafile
    ON dataversions(datafile_uuid);
CREATE INDEX IF NOT EXISTS idx_dataversions_source
    ON dataversions(source_version_uuid);
"""
