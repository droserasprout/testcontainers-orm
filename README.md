# testcontainers-orm

This package contains various ORM integrations for `testcontainers` and `unittest` framework making it easy to run tests on real database and ensure migrations integrity.

## Key features 

* Atomic test cases for SQLAlchemy and Tortoise ORM. Schema is being recreated from scratch for each test.
* A single database container used during interpreter lifespan.
* Test cases for comparing schema generated from models with Alembic migrations
* Some dirty hacks to make these things work with MySQL

## Installation

```shell-script
make install DEV=0
make build
```
