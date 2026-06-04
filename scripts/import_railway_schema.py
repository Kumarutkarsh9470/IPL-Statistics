"""
Import the IPL database schema into Railway MySQL.

Usage (PowerShell):
    python .\scripts\import_railway_schema.py --url "mysql://root:password@host:port/railway"

This script reads `database design/mysql_schema.sql` and executes all SQL statements.
"""
import argparse
from pathlib import Path
from urllib.parse import urlparse

import mysql.connector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import the IPL schema into Railway MySQL."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Full MySQL connection URL, e.g. mysql://root:pwd@host:port/railway",
    )
    parser.add_argument(
        "--schema",
        default="database design/mysql_schema.sql",
        help="Path to schema SQL file",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    schema_path = Path(args.schema)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    parsed = urlparse(args.url)
    if parsed.scheme not in ("mysql", "mysql+mysqlconnector"):
        raise ValueError("URL must begin with mysql:// or mysql+mysqlconnector://")

    user = parsed.username
    password = parsed.password or ""
    host = parsed.hostname
    port = parsed.port or 3306
    database = parsed.path.lstrip("/") or None

    print(f"Connecting to MySQL host={host} port={port} user={user}")
    connection = mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )

    sql = schema_path.read_text(encoding="utf-8")
    statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
    print(f"Executing {len(statements)} SQL statements...")

    cursor = connection.cursor()
    for stmt in statements:
        cursor.execute(stmt)
    connection.commit()

    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Schema imported successfully. Tables created: {len(tables)}")
    for table in tables:
        print(f"  - {table}")

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
