import os.path

from sqlalchemy import TIMESTAMP  # type: ignore
from sqlalchemy import Column  # type: ignore
from sqlalchemy import Integer  # type: ignore
from sqlalchemy import Numeric  # type: ignore
from sqlalchemy import String  # type: ignore
from sqlalchemy import text  # type: ignore
from typing_extensions import Type

from testcontainers_orm.sqlalchemy import Base
from testcontainers_orm.sqlalchemy import Storage
from testcontainers_orm.sqlalchemy import _SQLAlchemyAlembicTestCase
from testcontainers_orm.utils import classproperty


class TestStorage(Storage):
    pass


class Item(Base):
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True)
    name = Column(String(10), nullable=False)
    price = Column(Numeric(precision=20, scale=10), nullable=True)
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
    )


class Alembic57SQLAlchemyTest(_SQLAlchemyAlembicTestCase):
    IMAGE = 'mysql/mysql-server:5.7'

    @classproperty
    def DECLARATIVE_BASE(self) -> Type:
        return Base

    @classproperty
    def STORAGE_CLASS(self) -> Type[Storage]:
        return TestStorage

    @classproperty
    def PROJECT_PATH(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')

    @classproperty
    def ALEMBIC_PATH(self) -> str:
        return 'tests/test_testcontainers_orm/alembic'

    @classproperty
    def ALEMBIC_CONFIG_PATH(self) -> str:
        return 'tests/test_testcontainers_orm/alembic.ini'


class Alembic80SQLAlchemyTest(_SQLAlchemyAlembicTestCase):
    IMAGE = 'mysql/mysql-server:8.0'

    @classproperty
    def DECLARATIVE_BASE(self) -> Type:
        return Base

    @classproperty
    def STORAGE_CLASS(self) -> Type[Storage]:
        return TestStorage

    @classproperty
    def PROJECT_PATH(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')

    @classproperty
    def ALEMBIC_PATH(self) -> str:
        return 'tests/test_testcontainers_orm/alembic'

    @classproperty
    def ALEMBIC_CONFIG_PATH(self) -> str:
        return 'tests/test_testcontainers_orm/alembic.ini'
