#!/bin/bash

# Docker Management Script for Project Catalog
# This script provides easy commands to manage the application running in Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to check if services are running
check_services() {
    if ! docker-compose ps | grep -q "Up"; then
        print_warning "Docker services don't appear to be running."
        print_status "Starting services with: docker-compose up -d"
        docker-compose up -d
        sleep 10
    fi
}

# Function to load taxonomy
load_taxonomy() {
    print_status "Loading canonical taxonomy into the database..."
    
    # Run the taxonomy loading script in the web container
    docker-compose exec web python /app/scripts/load_taxonomy.py
    
    if [ $? -eq 0 ]; then
        print_success "Taxonomy loaded successfully!"
    else
        print_error "Failed to load taxonomy. Check the logs above for details."
        exit 1
    fi
}

# Function to run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    docker-compose exec web flask db upgrade
    
    if [ $? -eq 0 ]; then
        print_success "Migrations completed successfully!"
    else
        print_error "Failed to run migrations. Check the logs above for details."
        exit 1
    fi
}

# Function to check taxonomy status
check_taxonomy() {
    print_status "Checking taxonomy status..."
    
    docker-compose exec web python -c "
from src.catalog import create_app
from src.catalog.models.keyword import KeywordTaxonomy

app = create_app()
with app.app_context():
    count = KeywordTaxonomy.query.count()
    print(f'Canonical taxonomy terms in database: {count}')
    
    if count > 0:
        # Show some sample categories
        categories = KeywordTaxonomy.query.with_entities(KeywordTaxonomy.primary_category).distinct().limit(5).all()
        print('Sample categories:')
        for cat in categories:
            print(f'  - {cat[0]}')
    else:
        print('No taxonomy terms found. Run: ./docker-manage.sh load-taxonomy')
"
}

# Function to show logs
show_logs() {
    local service=${1:-web}
    print_status "Showing logs for service: $service"
    docker-compose logs -f "$service"
}

# Function to open shell in container
shell() {
    local service=${1:-web}
    print_status "Opening shell in $service container..."
    docker-compose exec "$service" /bin/bash
}

# Function to restart services
restart() {
    print_status "Restarting Docker services..."
    docker-compose restart
    print_success "Services restarted!"
}

# Function to show help
show_help() {
    echo "Docker Management Script for Project Catalog"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  load-taxonomy     Load the canonical taxonomy from CSV into the database"
    echo "  check-taxonomy    Check the current taxonomy status in the database"
    echo "  migrate          Run database migrations"
    echo "  logs [service]   Show logs for a service (default: web)"
    echo "  shell [service]  Open a shell in a container (default: web)"
    echo "  restart          Restart all services"
    echo "  help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 load-taxonomy              # Load taxonomy into database"
    echo "  $0 check-taxonomy             # Check taxonomy status"
    echo "  $0 logs web                   # Show web service logs"
    echo "  $0 shell celery-worker        # Open shell in celery worker"
    echo ""
}

# Main script logic
case "${1:-help}" in
    "load-taxonomy")
        check_docker
        check_services
        load_taxonomy
        ;;
    "check-taxonomy")
        check_docker
        check_services
        check_taxonomy
        ;;
    "migrate")
        check_docker
        check_services
        run_migrations
        ;;
    "logs")
        check_docker
        show_logs "$2"
        ;;
    "shell")
        check_docker
        check_services
        shell "$2"
        ;;
    "restart")
        check_docker
        restart
        ;;
    "help"|*)
        show_help
        ;;
esac
