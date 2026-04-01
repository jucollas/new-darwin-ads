-- PostgreSQL initialization: create isolated schemas for each service
-- This runs automatically when the postgres container starts for the first time

CREATE SCHEMA IF NOT EXISTS campaign_schema;
CREATE SCHEMA IF NOT EXISTS publishing_schema;
CREATE SCHEMA IF NOT EXISTS analytics_schema;
CREATE SCHEMA IF NOT EXISTS genetic_schema;
CREATE SCHEMA IF NOT EXISTS notification_schema;

-- Grant usage to the app user
GRANT USAGE ON SCHEMA campaign_schema TO adgen;
GRANT USAGE ON SCHEMA publishing_schema TO adgen;
GRANT USAGE ON SCHEMA analytics_schema TO adgen;
GRANT USAGE ON SCHEMA genetic_schema TO adgen;
GRANT USAGE ON SCHEMA notification_schema TO adgen;

-- Grant all privileges on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA campaign_schema GRANT ALL ON TABLES TO adgen;
ALTER DEFAULT PRIVILEGES IN SCHEMA publishing_schema GRANT ALL ON TABLES TO adgen;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics_schema GRANT ALL ON TABLES TO adgen;
ALTER DEFAULT PRIVILEGES IN SCHEMA genetic_schema GRANT ALL ON TABLES TO adgen;
ALTER DEFAULT PRIVILEGES IN SCHEMA notification_schema GRANT ALL ON TABLES TO adgen;
