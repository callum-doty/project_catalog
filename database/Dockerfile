FROM postgres:14

# Install build dependencies for pgvector
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-14

# Clone pgvector repository
RUN git clone --branch v0.4.0 https://github.com/pgvector/pgvector.git /tmp/pgvector

# Build and install pgvector
RUN cd /tmp/pgvector && \
    make && \
    make install

# Clean up
RUN apt-get remove -y build-essential git postgresql-server-dev-14 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/pgvector