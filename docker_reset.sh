#!/bin/bash
# save as docker_reset.sh

echo "Clearing database..."
docker exec project_catalog-db-1 psql -U custom_user -d catalog_db -c "TRUNCATE TABLE dropbox_syncs CASCADE;"
docker exec project_catalog-db-1 psql -U custom_user -d catalog_db -c "TRUNCATE TABLE llm_keywords CASCADE;"
docker exec project_catalog-db-1 psql -U custom_user -d catalog_db -c "TRUNCATE TABLE classifications CASCADE;"
docker exec project_catalog-db-1 psql -U custom_user -d catalog_db -c "TRUNCATE TABLE design_elements CASCADE;"
docker exec project_catalog-db-1 psql -U custom_user -d catalog_db -c "TRUNCATE TABLE extracted_text CASCADE;"
docker exec project_catalog-db-1 psql -U custom_user -d catalog_db -c "TRUNCATE TABLE llm_analysis CASCADE;"
docker exec project_catalog-db-1 psql -U custom_user -d catalog_db -c "TRUNCATE TABLE documents CASCADE;"
docker exec project_catalog-db-1 psql -U custom_user -d catalog_db -c "TRUNCATE TABLE batch_jobs CASCADE;"

echo "Clearing MinIO storage..."
# Run a one-off container to clear MinIO
docker run --rm --network project_catalog_default minio/mc \
  sh -c "mc config host add myminio http://project_catalog-minio-1:9000 minioaccess miniosecret && \
         mc rm --recursive --force myminio/documents && \
         mc mb --ignore-existing myminio/documents"

echo "Reset complete!"