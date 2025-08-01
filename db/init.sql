-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create gps_trace table matching ingestion code
CREATE TABLE IF NOT EXISTS gps_trace (
    id SERIAL PRIMARY KEY,
    drone_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    location GEOGRAPHY(Point, 4326) NOT NULL,
    altitude_meters DOUBLE PRECISION,
    agl_meters DOUBLE PRECISION,
    heading_deg DOUBLE PRECISION
);

