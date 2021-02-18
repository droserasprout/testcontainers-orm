import atexit
import time
import unittest
from typing import Optional

import redis.exceptions
from redis import Redis
from testcontainers.redis import RedisContainer  # type: ignore

from testcontainers_orm.config import RedisConfig

redis_container: Optional[  # pylint: disable=unsubscriptable-object
    RedisContainer
] = None


# NOTE: This class left private intentionally. Otherwise it will be discovered by nosetests.
class _RedisTestCase(unittest.TestCase):
    """Base class for tests which use redis database.

    Redis container is created once per interpreter's lifespan, but databases are flushed after each test.
    """

    HOST = '127.0.0.1'

    @classmethod
    def setUpClass(cls) -> None:
        global redis_container
        if not redis_container:
            redis_container = cls._create_redis_container()
            redis_container.start()
            cls._wait_for_connection()
            atexit.register(redis_container.stop)

    def tearDown(self) -> None:
        self.drop_schema()

    def drop_schema(self) -> None:
        self.get_client().flushall()

    @classmethod
    def get_config(cls) -> RedisConfig:
        return RedisConfig(
            host=cls.HOST,
            port=cls._get_port(),
        )

    @classmethod
    def get_client(cls) -> Redis:
        config = cls.get_config()
        return Redis(
            host=config.host,
            port=config.port,
        )

    @classmethod
    def _create_redis_container(cls) -> RedisContainer:
        container = RedisContainer()
        return container

    @classmethod
    def _get_port(cls) -> int:
        if redis_container is None:
            raise RuntimeError('Redis container is not running')
        return int(redis_container.get_exposed_port(redis_container.port_to_expose))

    @classmethod
    def _wait_for_connection(cls) -> None:
        client = cls.get_client()
        while True:
            try:
                client.ping()
                break
            except redis.exceptions.ConnectionError:
                time.sleep(0.1)
