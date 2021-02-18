import asyncio
from typing import Any

import tortoise.backends.mysql.schema_generator  # type: ignore
from aiomysql.connection import Connection  # type: ignore
from pymysql import OperationalError


# FIXME: https://github.com/aio-libs/aiomysql/issues/454 (merged, awaits 0.0.21)
def patch_aiomysql():
    async def _read_bytes(self, num_bytes):
        try:
            data = await self._reader.readexactly(num_bytes)
        except asyncio.exceptions.IncompleteReadError as e:
            msg = "Lost connection to MySQL server during query"
            raise OperationalError(2013, msg) from e
        except (IOError, OSError) as e:
            msg = "Lost connection to MySQL server during query (%s)" % (e,)
            raise OperationalError(2013, msg) from e
        return data

    Connection._read_bytes = _read_bytes


def _column_default_generator(
    self,
    table: str,
    column: str,
    default: Any,
    auto_now_add: bool = False,
    auto_now: bool = False,
) -> str:

    """Patch schema generation to allow using TIMESTAMP type instead of DATETIME(6)."""
    default_str = " DEFAULT"
    if not (auto_now or auto_now_add):
        default_str += f" {default}"
    else:
        # FIXME: Wrong default for TIMESTAMP field
        if auto_now_add:
            default_str += " CURRENT_TIMESTAMP()"
        if auto_now:
            default_str += " ON UPDATE CURRENT_TIMESTAMP()"
    return default_str


def apply_mysql_hacks():
    patch_aiomysql()
    tortoise.backends.mysql.schema_generator.MySQLSchemaGenerator._column_default_generator = _column_default_generator  # type: ignore
