from typing import Optional

from db_adapters.base import BaseDBAdapter


def get_adapter(db_type: str, connection_string: str) -> Optional[BaseDBAdapter]:
    db_type_lower = db_type.lower()
    if db_type_lower in ("mysql", "mariadb"):
        from db_adapters.mysql_adapter import MySQLAdapter
        return MySQLAdapter(connection_string)
    if db_type_lower in ("postgresql", "postgres", "pg"):
        from db_adapters.postgresql_adapter import PostgreSQLAdapter
        return PostgreSQLAdapter(connection_string)
    return None


__all__ = ["BaseDBAdapter", "get_adapter"]
