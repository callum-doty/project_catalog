# Use the official MinIO image from Docker Hub
FROM minio/minio:RELEASE.2023-05-04T21-44-30Z

# Expose the MinIO API port and Console port
EXPOSE 9000
EXPOSE 9001

# The default command is already `minio server /data --console-address :9001`
# which is what we specified in render.yaml.
# We can add a healthcheck here if desired.
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9000/minio/health/live || exit 1

# No explicit CMD or ENTRYPOINT needed as the base image provides it.
