-- init.sql
CREATE USER custom_user WITH PASSWORD 'strong_password';
ALTER USER custom_user WITH SUPERUSER;
CREATE DATABASE catalog_db;
GRANT ALL PRIVILEGES ON DATABASE catalog_db TO custom_user;