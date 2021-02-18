from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus


@dataclass
class RedisConfig:
    host: str = 'redis'
    port: int = 6379
    password: Optional[str] = None


@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    database: str
    driver: str = 'mysql+mysqlconnector'
    password: str = ''
    echo: bool = False
    isolation_level: str = 'READ COMMITTED'
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    charset = 'utf8'

    @property
    def connection_string(self) -> str:
        return f'{self.driver}://{self.user}:{quote_plus(self.password)}@{self.host}:{self.port}/{self.database}?charset={self.charset}'

    # NOTE: Connection string in Alembic config must be unquoted
    @property
    def connection_string_unquoted(self) -> str:
        return f'{self.driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}'
