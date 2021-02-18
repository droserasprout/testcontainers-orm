import atexit
import unittest
from abc import abstractmethod
from typing import Optional

from testcontainers.core.generic import DbContainer  # type: ignore
from testcontainers.mysql import MySqlContainer  # type: ignore

from testcontainers_orm.config import DatabaseConfig

# NOTE: Container object is a singleton which will be used in all tests inherited from DatabaseTestCase and stopped after
# NOTE: all tests are completed.
db_container: Optional[DbContainer] = None  # pylint: disable=unsubscriptable-object


class _DatabaseTestCase(unittest.TestCase):
    """Base class for test cases which use Docker database containers."""

    DRIVER = 'mysql+pymysql'
    HOST = '127.0.0.1'
    USER = 'root'
    PASSWORD = 'test'
    DATABASE = 'test'

    @classmethod
    @abstractmethod
    def _create_db_container(cls) -> DbContainer:
        pass

    @classmethod
    @abstractmethod
    def _get_connection_url(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def _get_port(cls) -> int:
        pass

    @classmethod
    def setUpClass(cls) -> None:
        global db_container
        if not db_container:
            db_container = cls._create_db_container()
            db_container.start()
            atexit.register(db_container.stop)

    @classmethod
    def get_config(cls) -> DatabaseConfig:
        return DatabaseConfig(
            driver=cls.DRIVER,
            host=cls.HOST,
            port=cls._get_port(),
            user=cls.USER,
            password=cls.PASSWORD,
            database=cls.DATABASE,
        )


class _MySQLDatabaseTestCase(_DatabaseTestCase):
    IMAGE = 'mysql/mysql-server:8.0'

    @classmethod
    def _create_db_container(cls) -> MySqlContainer:
        return MySqlContainer(
            cls.IMAGE,
            MYSQL_USER=cls.USER,
            MYSQL_ROOT_PASSWORD=cls.PASSWORD,
        ).with_env('MYSQL_ROOT_HOST', '%')

    @classmethod
    def _get_connection_url(cls) -> str:
        if db_container is None:
            raise RuntimeError('Database container is not running')
        return db_container.get_connection_url()

    @classmethod
    def _get_port(cls) -> int:
        if db_container is None:
            raise RuntimeError('Database container is not running')
        return int(db_container.get_exposed_port(db_container.port_to_expose))


class _LegacyMySQLDatabaseTestCase(_MySQLDatabaseTestCase):
    IMAGE = 'mysql/mysql-server:5.7'
