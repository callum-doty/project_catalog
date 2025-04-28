#!/bin/bash
# run_migration.sh

# Add project directory to Python path
export PYTHONPATH=$(pwd):$PYTHONPATH

# Run the migration
flask db upgrade

# If that fails, try direct alembic command
if [ $? -ne 0 ]; then
    echo "Flask migration failed, trying alembic directly..."
    PYTHONPATH=$(pwd) alembic -c migrations/alembic.ini upgrade head
fi