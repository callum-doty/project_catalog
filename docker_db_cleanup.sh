#!/bin/bash
# Docker Database Cleanup Script for Document Catalog
# This script runs the db_cleanup.py script within the Docker environment

# Default settings
DB_HOST="db"
DB_PORT="5432"
DB_NAME="catalog_db"
DB_USER="custom_user"
DB_PASSWORD="strong_password"
DOCKER_SERVICE="web"  # The service in docker-compose that has access to the database
SCRIPT_PATH="/app/db_cleanup.py"  # Path to the cleanup script in the container

# Help text
function show_help {
    echo "Docker Database Cleanup Script"
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help                Show this help message"
    echo "  -d, --dry-run             Perform a dry run without making changes"
    echo "  -y, --yes                 Skip confirmation prompt"
    echo "  -s, --schema              Print database schema before cleanup"
    echo "  --host HOST               Database host address (default: $DB_HOST)"
    echo "  --port PORT               Database port (default: $DB_PORT)"
    echo "  --db DB_NAME              Database name (default: $DB_NAME)"
    echo "  --user USER               Database user (default: $DB_USER)"
    echo "  --password PASSWORD       Database password"
    echo "  --docker-service SERVICE  Docker service to use (default: $DOCKER_SERVICE)"
    echo "  --script-path PATH        Path to cleanup script in container (default: $SCRIPT_PATH)"
    echo ""
    exit 0
}

# Parse arguments
SCRIPT_ARGS=""
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            show_help
            ;;
        -d|--dry-run)
            SCRIPT_ARGS="$SCRIPT_ARGS --dry-run"
            shift
            ;;
        -y|--yes)
            SCRIPT_ARGS="$SCRIPT_ARGS --yes"
            shift
            ;;
        -s|--schema)
            SCRIPT_ARGS="$SCRIPT_ARGS --schema"
            shift
            ;;
        --host)
            DB_HOST="$2"
            shift 2
            ;;
        --port)
            DB_PORT="$2"
            shift 2
            ;;
        --db)
            DB_NAME="$2"
            shift 2
            ;;
        --user)
            DB_USER="$2"
            shift 2
            ;;
        --password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        --docker-service)
            DOCKER_SERVICE="$2"
            shift 2
            ;;
        --script-path)
            SCRIPT_PATH="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

# Check if Docker is running
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

if ! docker ps &> /dev/null; then
    echo "Error: Docker daemon is not running or you don't have permission to access it"
    exit 1
fi

# Check if the Docker service exists
if ! docker-compose ps $DOCKER_SERVICE &> /dev/null; then
    echo "Error: Docker service '$DOCKER_SERVICE' does not exist or is not running"
    echo "Available services:"
    docker-compose ps --services
    exit 1
fi

# Copy the cleanup script to the container
echo "Copying db_cleanup.py to the container..."
if [ -f "./db_cleanup.py" ]; then
    docker cp ./db_cleanup.py $(docker-compose ps -q $DOCKER_SERVICE):$SCRIPT_PATH
    
    # Make the script executable
    docker-compose exec $DOCKER_SERVICE chmod +x $SCRIPT_PATH
else
    echo "Error: db_cleanup.py not found in the current directory"
    exit 1
fi

# Run the script in the container
echo "Running cleanup script in Docker container..."
docker-compose exec $DOCKER_SERVICE python $SCRIPT_PATH \
    --host $DB_HOST \
    --port $DB_PORT \
    --db $DB_NAME \
    --user $DB_USER \
    --password $DB_PASSWORD \
    $SCRIPT_ARGS

# Check the exit code
if [ $? -eq 0 ]; then
    echo "Database cleanup completed successfully"
else
    echo "Database cleanup failed"
    exit 1
fi