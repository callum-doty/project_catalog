#!/usr/bin/env python3
"""
Database Cleanup Script for Document Catalog

This script safely clears all data from the database tables without
dropping tables, preserving the database schema and relationships.

Usage:
    python db_cleanup.py
"""

import os
import sys
import logging
from datetime import datetime
import argparse
import psycopg2
from psycopg2 import sql
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"db_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("db_cleanup")

# Define the order to truncate tables based on foreign key dependencies
# Tables with foreign keys should be deleted before the tables they reference
TABLE_ORDER = [
    # Child tables first (those with foreign keys)
    "document_keywords",
    "document_scorecards",
    "keyword_synonyms",
    "search_feedback",
    "llm_keywords",
    "entities",
    "communication_focus",
    "design_elements",
    "classifications",
    "extracted_text",
    "llm_analysis",
    "dropbox_syncs",

    # Then parent tables
    "documents",
    "keyword_taxonomy",
    "batch_jobs"
]


def get_db_connection(host=None, port=None, database=None, user=None, password=None):
    """Connect to the PostgreSQL database"""
    # First priority: command line arguments
    db_params = {}
    if host:
        db_params['host'] = host
    if port:
        db_params['port'] = port
    if database:
        db_params['database'] = database
    if user:
        db_params['user'] = user
    if password:
        db_params['password'] = password

    # Second priority: DATABASE_URL environment variable
    if not db_params and os.environ.get('DATABASE_URL'):
        logger.info(f"Using DATABASE_URL environment variable")
        return psycopg2.connect(os.environ.get('DATABASE_URL'))

    # Third priority: individual environment variables
    if 'host' not in db_params:
        db_params['host'] = os.environ.get(
            'DB_HOST') or os.environ.get('PGHOST', 'localhost')
    if 'port' not in db_params:
        db_params['port'] = os.environ.get(
            'DB_PORT') or os.environ.get('PGPORT', '5432')
    if 'database' not in db_params:
        db_params['database'] = os.environ.get(
            'DB_NAME') or os.environ.get('PGDATABASE', 'catalog_db')
    if 'user' not in db_params:
        db_params['user'] = os.environ.get(
            'DB_USER') or os.environ.get('PGUSER', 'custom_user')
    if 'password' not in db_params:
        db_params['password'] = os.environ.get(
            'DB_PASSWORD') or os.environ.get('PGPASSWORD', 'strong_password')

    # Fourth priority: try SQLALCHEMY_DATABASE_URI environment variable (common in Flask apps)
    sqlalchemy_uri = os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not db_params.get('host') and sqlalchemy_uri and 'postgresql://' in sqlalchemy_uri:
        logger.info(f"Using SQLALCHEMY_DATABASE_URI environment variable")
        return psycopg2.connect(sqlalchemy_uri)

    logger.info(
        f"Connecting to database at {db_params['host']}:{db_params['port']} as {db_params['user']}")
    return psycopg2.connect(**db_params)


def get_all_tables(conn):
    """Get all tables in the public schema"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        tables = [row[0] for row in cur.fetchall()]
    return tables


def get_sequences(conn):
    """Get all sequences in the database"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT sequence_name FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
        """)
        sequences = [row[0] for row in cur.fetchall()]
    return sequences


def get_database_schema(conn):
    """Get the database schema for tables in the public schema"""
    schema_info = {}

    # Get all tables
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]

        # For each table, get column information
        for table in tables:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            columns = [(col[0], col[1], col[2]) for col in cur.fetchall()]
            schema_info[table] = columns

    return schema_info


def print_database_schema(conn):
    """Print the database schema"""
    schema = get_database_schema(conn)

    logger.info("Database Schema:")
    logger.info("=" * 60)

    for table, columns in schema.items():
        logger.info(f"Table: {table}")
        logger.info("-" * 60)
        for col_name, col_type, nullable in columns:
            nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
            logger.info(f"  {col_name:30} {col_type:20} {nullable_str}")
        logger.info("")


def truncate_table(conn, table_name):
    """Safely truncate a table"""
    with conn.cursor() as cur:
        # Use SQL composition to safely handle table names
        query = sql.SQL("TRUNCATE TABLE {} CASCADE").format(
            sql.Identifier(table_name))
        logger.info(f"Running: {query.as_string(conn)}")
        try:
            cur.execute(query)
            logger.info(f"Successfully truncated table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Error truncating table {table_name}: {str(e)}")
            return False


def reset_sequence(conn, sequence_name):
    """Reset a sequence to 1"""
    with conn.cursor() as cur:
        # Use SQL composition to safely handle sequence names
        query = sql.SQL("ALTER SEQUENCE {} RESTART WITH 1").format(
            sql.Identifier(sequence_name))
        logger.info(f"Running: {query.as_string(conn)}")
        try:
            cur.execute(query)
            logger.info(f"Reset sequence: {sequence_name}")
            return True
        except Exception as e:
            logger.error(f"Error resetting sequence {sequence_name}: {str(e)}")
            return False


def cleanup_database(conn, dry_run=False):
    """Perform the database cleanup"""
    logger.info("Starting database cleanup process...")

    # Get all tables from the database
    all_tables = get_all_tables(conn)
    logger.info(f"Found {len(all_tables)} tables in the database")

    # Check if any tables from our order list are missing
    missing_tables = set(TABLE_ORDER) - set(all_tables)
    if missing_tables:
        logger.warning(
            f"Some tables in the cleanup order are not in the database: {missing_tables}")

    # Add any tables from the database that aren't in our order list
    tables_not_in_order = set(all_tables) - set(TABLE_ORDER)
    if tables_not_in_order:
        logger.warning(
            f"Some tables in the database are not in the cleanup order: {tables_not_in_order}")
        logger.warning("These tables will be truncated after the known tables")

    # Create the final ordered list of tables to truncate
    truncate_list = [
        table for table in TABLE_ORDER if table in all_tables] + list(tables_not_in_order)

    logger.info(
        f"Will truncate {len(truncate_list)} tables in the following order:")
    for idx, table in enumerate(truncate_list, 1):
        logger.info(f"  {idx}. {table}")

    # Get sequences to reset
    sequences = get_sequences(conn)
    logger.info(f"Found {len(sequences)} sequences to reset")

    if dry_run:
        logger.info("DRY RUN - No changes will be made to the database")
        return

    # Truncate tables in order
    success_count = 0
    for table in truncate_list:
        if truncate_table(conn, table):
            success_count += 1

    # Reset sequences
    seq_success = 0
    for sequence in sequences:
        if reset_sequence(conn, sequence):
            seq_success += 1

    # Log summary
    logger.info("=" * 50)
    logger.info(f"Database cleanup summary:")
    logger.info(f"  Tables truncated: {success_count}/{len(truncate_list)}")
    logger.info(f"  Sequences reset: {seq_success}/{len(sequences)}")
    logger.info("=" * 50)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Database Cleanup Script')
    parser.add_argument('--dry-run', action='store_true',
                        help='Perform a dry run without making changes')
    parser.add_argument('--yes', action='store_true',
                        help='Skip confirmation prompt')
    parser.add_argument('--schema', action='store_true',
                        help='Print database schema before cleanup')

    # Add database connection arguments
    parser.add_argument(
        '--host', help='Database host address (default: localhost)')
    parser.add_argument('--port', help='Database port (default: 5432)')
    parser.add_argument('--db', dest='database',
                        help='Database name (default: catalog_db)')
    parser.add_argument('--user', help='Database user (default: custom_user)')
    parser.add_argument('--password', help='Database password')

    args = parser.parse_args()

    # Show script title with current timestamp
    title = f"Database Cleanup Script - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    logger.info("=" * 70)
    logger.info(title.center(70))
    logger.info("=" * 70)

    # Connect to the database
    try:
        conn = get_db_connection(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password
        )
        logger.info("Successfully connected to the database")
    except Exception as e:
        logger.error(f"Failed to connect to the database: {str(e)}")
        logger.error(
            "Check your connection parameters and make sure the database is accessible")
        logger.error(
            "You can specify connection parameters with --host, --port, --db, --user, and --password")
        return 1

    # Print schema if requested
    if args.schema:
        print_database_schema(conn)

    # Print warning
    logger.warning("")
    logger.warning("!!! WARNING !!!")
    logger.warning("This script will delete ALL DATA from the database.")
    logger.warning("This action CANNOT be undone.")
    logger.warning("")

    # In dry run mode, display what would happen
    if args.dry_run:
        logger.info("DRY RUN MODE: No changes will be made to the database")

    # Ask for confirmation if not already provided
    if not args.yes and not args.dry_run:
        confirm = input(
            "Are you sure you want to proceed? Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            logger.info("Cleanup cancelled by user")
            return 0

    try:
        # Get table counts before cleanup (for verification)
        all_tables = get_all_tables(conn)
        table_counts_before = {}

        if not args.dry_run:
            with conn.cursor() as cur:
                for table in all_tables:
                    try:
                        cur.execute(
                            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
                        count = cur.fetchone()[0]
                        table_counts_before[table] = count
                    except Exception as e:
                        logger.error(
                            f"Error getting count for table {table}: {str(e)}")
                        table_counts_before[table] = "ERROR"

        # Perform cleanup
        cleanup_database(conn, args.dry_run)

        # Commit changes if not a dry run
        if not args.dry_run:
            conn.commit()
            logger.info("All changes committed successfully")

            # Verify tables are empty
            table_counts_after = {}
            with conn.cursor() as cur:
                for table in all_tables:
                    try:
                        cur.execute(
                            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
                        count = cur.fetchone()[0]
                        table_counts_after[table] = count
                    except Exception as e:
                        logger.error(
                            f"Error getting count for table {table}: {str(e)}")
                        table_counts_after[table] = "ERROR"

            # Print before/after counts
            logger.info("")
            logger.info("Table Row Counts (Before → After)")
            logger.info("=" * 50)
            for table in all_tables:
                before = table_counts_before.get(table, "N/A")
                after = table_counts_after.get(table, "N/A")
                logger.info(f"{table:30} {before:10} → {after:10}")
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}")
        logger.error(traceback.format_exc())
        conn.rollback()
        logger.info("All changes rolled back due to error")
        return 1
    finally:
        conn.close()
        logger.info("Database connection closed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
