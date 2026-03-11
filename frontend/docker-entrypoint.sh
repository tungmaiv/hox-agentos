#!/bin/sh
# Entrypoint script for frontend dev container
# Adds Keycloak CA cert to system trust store at runtime

# Add Keycloak cert to system CA bundle if it exists
if [ -f /app/certs/keycloak.crt ]; then
    cat /app/certs/keycloak.crt >> /etc/ssl/certs/ca-certificates.crt 2>/dev/null || true
fi

# Execute the original command (pnpm dev)
exec "$@"
