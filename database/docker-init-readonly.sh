#!/bin/bash
set -eu

case "${MYSQL_DATABASE}" in
  *[!A-Za-z0-9_]*|'')
    echo "MYSQL_DATABASE must contain only letters, digits, and underscores" >&2
    exit 1
    ;;
esac

case "${MYSQL_USER}" in
  *[!A-Za-z0-9_]*|'')
    echo "MYSQL_USER must contain only letters, digits, and underscores" >&2
    exit 1
    ;;
esac

# The official image initially grants MYSQL_USER broad access to MYSQL_DATABASE.
# Replace it with the same read-only privileges used by the local native setup.
docker_process_sql --database=mysql <<SQL
REVOKE ALL PRIVILEGES, GRANT OPTION FROM '${MYSQL_USER}'@'%';
GRANT SELECT, SHOW VIEW ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
SQL
