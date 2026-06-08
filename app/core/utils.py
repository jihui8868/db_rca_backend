from uuid6 import uuid7


def generate_uuid7() -> str:
    return str(uuid7())


def build_connection_string(
    db_type: str,
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str,
) -> str:
    """
    根据数据库类型和连接参数生成连接字符串。

    支持的数据库类型：
    - mysql: mysql+pymysql://user:password@host:port/database
    - postgresql: postgresql://user:password@host:port/database
    - oracle: oracle://user:password@host:port/?service_name=database
    """
    if db_type.lower() == "mysql":
        return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type.lower() == "postgresql":
        return f"postgresql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type.lower() == "oracle":
        return f"oracle://{username}:{password}@{host}:{port}/?service_name={database_name}"
    else:
        # 默认格式
        return f"{db_type}://{username}:{password}@{host}:{port}/{database_name}"
