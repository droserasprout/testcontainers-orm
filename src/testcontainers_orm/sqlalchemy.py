import logging
import os.path
from abc import ABC
from contextlib import contextmanager
from datetime import timedelta
from typing import Generator
from typing import Generic
from typing import Optional
from typing import Set
from typing import Type
from typing import TypeVar

import alembic.command  # type: ignore
import alembic.config  # type: ignore
import sqlalchemy.exc  # type: ignore
import sqlalchemy.orm  # type: ignore
import typing_inspect  # type: ignore
from sqlalchemy import inspect  # type: ignore
from sqlalchemy.engine import Connection  # type: ignore
from sqlalchemy.engine import Engine
from sqlalchemy.engine import create_engine
from sqlalchemy.ext.declarative import as_declarative  # type: ignore
from sqlalchemy.orm import sessionmaker  # type: ignore
from sqlalchemy.orm.session import close_all_sessions  # type: ignore
from sqlalchemy_repr import RepresentableBase  # type: ignore

from testcontainers_orm.config import DatabaseConfig
from testcontainers_orm.database import _MySQLDatabaseTestCase
from testcontainers_orm.utils import classproperty

Session = sessionmaker()

# NOTE: https://github.com/dropbox/sqlalchemy-stubs/issues/40
Base = as_declarative()(RepresentableBase)


class Storage(sqlalchemy.orm.Session):
    ...


TStorage = TypeVar('TStorage', bound=Storage)


class EngineFactory(Generic[TStorage]):
    def __init__(self, config: DatabaseConfig) -> None:
        self._logger: logging.Logger = logging.getLogger(__name__)
        if config.driver == 'mysql':
            config.driver = 'mysql+pymysql'
        self._config: DatabaseConfig = config
        self._engine: Optional[Engine] = None

    def _create_engine(self) -> Engine:
        connection_string = self._config.connection_string
        engine = create_engine(
            connection_string,
            echo=self._config.echo,
            isolation_level=self._config.isolation_level,
            pool_recycle=self._config.pool_recycle,
            pool_pre_ping=self._config.pool_pre_ping,
        )
        return engine

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = self._create_engine()

        return self._engine


class ConnectionFactory(EngineFactory):
    def _create_connection(self) -> sqlalchemy.engine.base.Connection:
        engine = self._get_engine()

        return engine.connect()

    @contextmanager
    def create(self) -> Generator[Connection, None, None]:
        connection = self._create_connection()
        try:
            yield connection
        except Exception as exc:
            raise exc
        finally:
            connection.close()


class SessionFactory(EngineFactory[TStorage]):
    def _get_storage_class(self) -> Type[TStorage]:
        generic_type = typing_inspect.get_generic_type(self)
        type_parameters = typing_inspect.get_args(generic_type)
        return type_parameters[0]

    def _create_session(self) -> TStorage:
        engine = self._get_engine()
        storage_class = self._get_storage_class()
        session = storage_class(bind=engine, expire_on_commit=False)
        return session

    @contextmanager
    def create(self) -> Generator[TStorage, None, None]:
        session = self._create_session()
        try:
            yield session
            session.commit()
        except Exception as exc:
            session.rollback()
            raise exc
        finally:
            session.close()


class FakeEnum(sqlalchemy.types.Enum):
    def __init__(self, *args, **kwargs):
        kwargs = {**kwargs, 'create_constraint': False, 'native_enum': False}
        super().__init__(*args, **kwargs)


# NOTE: This class left private intentionally. Otherwise it will be discovered by nosetests.
class _SQLAlchemyTestCase(_MySQLDatabaseTestCase):
    # sqlalchemy.declarative_base instance. Used to create and drop database schema.

    @classproperty
    def DECLARATIVE_BASE(self) -> Type:
        """Declarative base SQLAlchemy models are inherited from."""
        return Base

    @classproperty
    def STORAGE_CLASS(self) -> Type[Storage]:
        # FIXME: Why configure this?
        """Storage class to use as session factory generic type."""
        return Storage

    def setUp(self) -> None:
        self.create_schema()

    def tearDown(self):
        close_all_sessions()
        self.drop_schema()

    def run(self, result=None):
        session_factory = SessionFactory[self.STORAGE_CLASS](self.get_config())
        with session_factory.create() as storage:
            self.storage = storage
            super().run(result)

            # NOTE: http://jira.b9prime.net:8080/browse/CORE-205
            self.storage = None

    @classmethod
    def create_schema(cls) -> None:
        cls.DECLARATIVE_BASE.metadata.create_all(cls._get_engine())

    @classmethod
    def drop_schema(cls) -> None:
        cls.DECLARATIVE_BASE.metadata.drop_all(cls._get_engine())

    @classmethod
    @contextmanager
    def get_connection(cls) -> Generator[Connection, None, None]:
        connection_factory = ConnectionFactory(cls.get_config())

        with connection_factory.create() as connection:
            yield connection

    @classmethod
    @contextmanager
    def get_session(cls) -> Generator[Storage, None, None]:
        session_factory = SessionFactory[Storage](cls.get_config())

        with session_factory.create() as session:
            yield session

    @classmethod
    def _get_engine(cls) -> Engine:
        return sqlalchemy.create_engine(cls._get_connection_url())

    @classmethod
    def recreate_database(cls, name: str) -> None:
        with cls.get_connection() as connection:
            connection.execute(f'DROP DATABASE IF EXISTS `{name}`;')
            connection.execute(f'CREATE DATABASE `{name}`;')


# NOTE: This class left private intentionally. Otherwise it will be discovered by nosetests.
class _SQLAlchemyAlembicTestCase(ABC, _SQLAlchemyTestCase):
    @classproperty
    def PROJECT_PATH(self) -> str:
        """Path to root project directory."""
        raise NotImplementedError

    @classproperty
    def ALEMBIC_PATH(self) -> str:
        """Relative path to 'alembic' directory (usually 'src/{project_name}/storage/alembic')."""
        raise NotImplementedError

    @classproperty
    def ALEMBIC_CONFIG_PATH(self) -> str:
        """Relative path to 'alembic.ini' config (usually 'src/{project_name}/storage/alembic.ini')."""
        raise NotImplementedError

    @classproperty
    def ALEMBIC_DATABASE(self) -> str:
        """Name of schema used for Alembic migrations."""
        return 'test_alembic'

    @classproperty
    def IGNORED_TABLES(self) -> Set[str]:
        """Set of table names ignored by all checks."""
        return {'alembic_version'}

    # Internal attributes for typehinting
    config: DatabaseConfig
    alembic_config: DatabaseConfig
    storage: Optional[sqlalchemy.orm.Session]
    alembic_storage: Optional[sqlalchemy.orm.Session]

    # Do not truncate long unittest diffs
    maxDiff = None

    # NOTE: We do not need to recreate schemas after every check. It will be done once in setUpClass and tearDownClass.
    def setUp(self) -> None:
        pass

    def tearDown(self):
        pass

    def run(self, result=None):
        session_factory = SessionFactory[self.STORAGE_CLASS](self.get_config())
        alembic_session_factory = SessionFactory[self.STORAGE_CLASS](
            self.get_alembic_config()
        )
        with session_factory.create() as storage:
            with alembic_session_factory.create() as alembic_storage:
                self.storage = storage
                self.alembic_storage = alembic_storage

                self.storage_inspector = inspect(self.storage.get_bind())
                self.alembic_inspector = inspect(self.alembic_storage.get_bind())

                super().run(result)

                self.storage = None
                self.alembic_storage = None

    @classmethod
    def get_alembic_config(cls) -> DatabaseConfig:
        config = cls.get_config()
        config.database = cls.ALEMBIC_DATABASE
        if config.driver == 'mysql':
            config.driver = 'mysql+pymysql'
        return config

    @classmethod
    def create_alembic_schema(cls) -> None:
        alembic_config = alembic.config.Config(
            os.path.join(cls.PROJECT_PATH, cls.ALEMBIC_CONFIG_PATH)
        )
        alembic_config.set_main_option(
            'script_location', os.path.join(cls.PROJECT_PATH, cls.ALEMBIC_PATH)
        )
        alembic_config.set_main_option(
            'sqlalchemy.url', cls.get_alembic_config().connection_string
        )
        alembic.command.upgrade(alembic_config, "head")

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.recreate_database(cls.ALEMBIC_DATABASE)
        cls.create_schema()
        cls.create_alembic_schema()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        cls.recreate_database(cls.ALEMBIC_DATABASE)
        cls.drop_schema()

    def test_tables_are_equal(self) -> None:
        alembic_tables = (
            set(self.alembic_inspector.get_table_names()) - self.IGNORED_TABLES
        )
        storage_tables = set(self.storage_inspector.get_table_names())

        self.assertSetEqual(alembic_tables, storage_tables)

    def test_table_options_are_equal(self) -> None:
        storage_tables = set(self.storage_inspector.get_table_names())

        for table in storage_tables:
            alembic_options = self.alembic_inspector.get_table_options(table)
            storage_options = self.storage_inspector.get_table_options(table)

            self.assertDictEqual(alembic_options, storage_options)

    def test_columns_are_equal(self) -> None:
        storage_tables = set(self.storage_inspector.get_table_names())

        for table in storage_tables:
            alembic_columns = sorted(
                self.alembic_inspector.get_columns(table), key=lambda c: c['name']
            )
            storage_columns = sorted(
                self.storage_inspector.get_columns(table), key=lambda c: c['name']
            )

            alembic_columns_names = [column['name'] for column in alembic_columns]
            storage_columns_names = [column['name'] for column in storage_columns]
            self.assertListEqual(alembic_columns_names, storage_columns_names)

            for alembic_column, storage_column in zip(alembic_columns, storage_columns):
                alembic_column = {
                    k: str(v) for k, v in alembic_column.items() if k != 'comment'
                }
                storage_column = {
                    k: str(v) for k, v in storage_column.items() if k != 'comment'
                }

                self.assertDictEqual(
                    alembic_column,
                    storage_column,
                    msg=f'Different column\'s attribute in the `{table}.{alembic_column["name"]}` column',
                )

    def test_foreign_keys_are_equal(self) -> None:
        storage_tables = set(self.storage_inspector.get_table_names())

        for table in storage_tables:
            alembic_fks = sorted(
                self.alembic_inspector.get_foreign_keys(table),
                key=lambda c: c['constrained_columns'],
            )
            storage_fks = sorted(
                self.storage_inspector.get_foreign_keys(table),
                key=lambda c: c['constrained_columns'],
            )

            # NOTE: We do not care about constraint names as both sqlalchemy and alembic generate them
            for fk in alembic_fks:
                del fk['name']
            for fk in storage_fks:
                del fk['name']

            self.assertListEqual(alembic_fks, storage_fks)

    def test_indexes_are_equal(self) -> None:
        storage_tables = set(self.storage_inspector.get_table_names())

        for table in storage_tables:
            alembic_indexes = sorted(
                self.alembic_inspector.get_indexes(table), key=lambda c: c['name']
            )
            storage_indexes = sorted(
                self.storage_inspector.get_indexes(table), key=lambda c: c['name']
            )

            self.assertListEqual(
                alembic_indexes,
                storage_indexes,
                msg=f'Different index in the `{table}` table',
            )

    def test_pk_constraints_are_equal(self) -> None:
        storage_tables = set(self.storage_inspector.get_table_names())

        for table in storage_tables:
            alembic_pk_constraint = self.alembic_inspector.get_pk_constraint(table)
            storage_pk_constraint = self.storage_inspector.get_pk_constraint(table)

            self.assertDictEqual(
                alembic_pk_constraint,
                storage_pk_constraint,
                msg=f'Different pk constraint in the `{table}` table',
            )

    def test_unique_constraints_are_equal(self) -> None:
        storage_tables = set(self.storage_inspector.get_table_names())

        for table in storage_tables:
            alembic_unique_constraints = sorted(
                self.alembic_inspector.get_unique_constraints(table),
                key=lambda c: c['name'],
            )

            storage_unique_constraints = sorted(
                self.storage_inspector.get_unique_constraints(table),
                key=lambda c: c['name'],
            )

            self.assertListEqual(
                alembic_unique_constraints,
                storage_unique_constraints,
                msg=f'Different unique constraint in the `{table}` table',
            )
