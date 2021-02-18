from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Optional
from unittest import IsolatedAsyncioTestCase

from tortoise import Tortoise  # type: ignore
from tortoise import fields
from tortoise.transactions import in_transaction  # type: ignore

from testcontainers_orm.config import DatabaseConfig
from testcontainers_orm.database import _MySQLDatabaseTestCase
from testcontainers_orm.sqlalchemy import _SQLAlchemyAlembicTestCase
from testcontainers_orm.sqlalchemy import _SQLAlchemyTestCase
from testcontainers_orm.utils import classproperty


class TimestampField(fields.DatetimeField):
    """MySQL TIMESTAMP field.

    ``auto_now`` and ``auto_now_add`` is exclusive.
    You can opt to set neither or only ONE of them.

    ``auto_now`` (bool):
        Always set to ``datetime.utcnow()`` on save.
    ``auto_now_add`` (bool):
        Set to ``datetime.utcnow()`` on first save only.
    """

    skip_to_python_if_native = False
    SQL_TYPE = "TIMESTAMP"

    class _db_mysql:
        SQL_TYPE = "TIMESTAMP"

    def to_python_value(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc)
        return datetime.utcfromtimestamp(value).replace(tzinfo=timezone.utc)

    @property
    def constraints(self) -> dict:
        data = {}
        if self.auto_now_add:
            data["readOnly"] = True
        return data


# NOTE: This class left private intentionally. Otherwise it will be discovered by nosetests.
class _TortoiseTestCase(_MySQLDatabaseTestCase, IsolatedAsyncioTestCase):
    @classproperty
    def MODELS_MODULE(self) -> str:
        """Qualified name of module containing Tortoise models (usually project.storage.models)."""
        raise NotImplementedError

    @classmethod
    def get_config(cls) -> DatabaseConfig:
        config = _MySQLDatabaseTestCase.get_config()
        config.driver = 'mysql'
        return config

    # NOTE: This method returns coroutine and thus should not override super().create_schema
    @classmethod
    async def create_tortoise_schema(cls) -> None:
        Tortoise._inited = False
        await Tortoise.init(
            db_url=cls.get_config().connection_string,
            modules={'models': [cls.MODELS_MODULE]},
        )
        await Tortoise.generate_schemas()

    @classmethod
    async def drop_tortoise_schema(cls) -> None:
        Tortoise._inited = False
        await Tortoise.init(
            db_url=cls.get_config().connection_string,
            modules={'models': [cls.MODELS_MODULE]},
        )
        async with in_transaction() as conn:
            # NOTE: Unable to reconnect on the next test otherwise.
            await conn.execute_query(f'''DROP SCHEMA {cls.get_config().database}''')
            await conn.execute_query(f'''CREATE SCHEMA {cls.get_config().database}''')

    async def asyncSetUp(self) -> None:
        await self.create_tortoise_schema()

    async def asyncTearDown(self) -> None:
        await self.drop_tortoise_schema()
        await Tortoise.close_connections()


# NOTE: This class left private intentionally. Otherwise it will be discovered by nosetests.
class _AlembicTortoiseTestCase(_TortoiseTestCase, _SQLAlchemyAlembicTestCase):
    """AlembicSQLAlchemyTestCase, but with Tortoise schema creation.

    SQLAlchemy class is reused as we use Alembic instead of Tortoise native migrations for consistency among projects.
    """

    @classmethod
    def setUpClass(cls) -> None:
        _SQLAlchemyTestCase.setUpClass()
        cls.recreate_database(cls.ALEMBIC_DATABASE)
        cls.create_alembic_schema()

    @classmethod
    def tearDownClass(cls) -> None:
        _SQLAlchemyTestCase.tearDownClass()
        cls.recreate_database(cls.ALEMBIC_DATABASE)

    # FIXME: Tortoise generates random index names on schema creation. Skip this test for now.
    def test_indexes_are_equal(self) -> None:
        pass

    # FIXME: Tortoise creates tables with correct charset, however alembic always returns latin1 as a default one.
    def test_table_options_are_equal(self) -> None:
        pass
