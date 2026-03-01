#!/bin/sh
# Fix permissions on mounted data directory
# (volume mount overrides Dockerfile ownership)
if [ -d /app/data ] && [ "$(stat -c '%u' /app/data)" != "$(id -u)" ]; then
    echo "Fixing /app/data permissions..."
fi

exec "$@"
