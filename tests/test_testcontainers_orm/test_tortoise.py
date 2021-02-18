import os.path

from tortoise import Model
from tortoise import fields  # type: ignore

from testcontainers_orm.tortoise import TimestampField
from testcontainers_orm.tortoise import _AlembicTortoiseTestCase
from testcontainers_orm.utils import classproperty


class Item(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(10, null=False)
    price = fields.DecimalField(20, 10, null=True)
    created_at = TimestampField(null=False, auto_now_add=True)
    updated_at = TimestampField(null=False, auto_now=True)

    class Meta:
        table = 'items'


class AlembicTortoiseTestCase(_AlembicTortoiseTestCase):
    @classproperty
    def MODELS_MODULE(self) -> str:
        return 'tests.test_testcontainers_orm.test_tortoise'

    @classproperty
    def PROJECT_PATH(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')

    @classproperty
    def ALEMBIC_PATH(self) -> str:
        return 'tests/test_testcontainers_orm/alembic'

    @classproperty
    def ALEMBIC_CONFIG_PATH(self) -> str:
        return 'tests/test_testcontainers_orm/alembic.ini'
