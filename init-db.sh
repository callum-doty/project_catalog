#!/bin/bash
# init-db.sh

echo "Waiting for PostgreSQL to start..."
sleep 10

echo "Running database migrations..."
flask db upgrade

echo "Database initialization complete!"