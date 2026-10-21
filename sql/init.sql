CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS bronze.offres (
    id          SERIAL PRIMARY KEY,
    source      TEXT NOT NULL,          -- 'rekrute' ou 'emploi_ma'
    url         TEXT NOT NULL UNIQUE,   -- évite les doublons
    payload     JSONB NOT NULL,         -- l'offre brute telle que scrapée
    scraped_at  TIMESTAMPTZ DEFAULT NOW()
);