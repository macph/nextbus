"""
Database model extensions for the nextbus package.
"""
from abc import abstractmethod

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.ext.compiler as sa_compiler

from nextbus import db
from nextbus.logger import app_logger

logger = app_logger.getChild("models")


def table_name(model):
    """ Returns column with literal name of model table. """
    return db.literal_column(f"'{model.__tablename__}'")


def iter_models(match=None):
    sa_registry = getattr(db.Model, "_sa_registry")
    class_registry = getattr(sa_registry, "_class_registry")
    for m in class_registry.values():
        if hasattr(m, "__table__") and (match is None or issubclass(m, match)):
            yield m


class _DropIndexes:
    """ Context manager for dropping and restoring indexes. """
    def __init__(self, bind=None, models=None, exclude_unique=False,
                 include_missing=False):
        self._bind = bind or db.engine
        self._models = list(models if models is not None else iter_models())
        self._exclude_unique = exclude_unique
        self._include_missing = include_missing
        self._dropped = set()

    def __enter__(self):
        for model in self._models:
            for index in model.__table__.indexes:
                self._drop_index(index)

    def _drop_index(self, index):
        if self._exclude_unique and index.unique:
            logger.info(f"Skipping unique index {index.name!r}")
            return

        logger.info(f"Dropping index {index.name!r}")
        try:
            index.drop(self._bind)
        except sqlalchemy.exc.ProgrammingError:
            logger.warning(
                f"Error dropping index {index.name!r}",
                exc_info=1
            )
            is_dropped = False
        else:
            is_dropped = True

        if is_dropped or self._include_missing:
            self._dropped.add(index)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        while self._dropped:
            index = self._dropped.pop()
            logger.info(f"Recreating index {index.name!r}")
            try:
                index.create(self._bind)
            except sqlalchemy.exc.ProgrammingError:
                logger.warning(
                    f"Error recreating index {index.name!r}",
                    exc_info=1
                )


def drop_indexes(bind=None, models=None, exclude_unique=False,
                 include_missing=False):
    """ Creates a context manager for dropping and restring specified indexes.
    """
    return _DropIndexes(bind, models, exclude_unique, include_missing)

class DerivedModel(db.Model):
    __abstract__ = True

    @classmethod
    @abstractmethod
    def insert_new(cls, connection):
        """ Returns a list of selectables which will be used to update
            model with new rows.
        """
        pass

    @classmethod
    def refresh(cls, connection):
        """ Delete existing rows and inserted updated rows from selectable. """
        columns = [c.key for c in cls.__table__.columns]
        connection.execute(cls.__table__.delete())
        for statement in cls.insert_new(connection):
            connection.execute(
                cls.__table__.insert().from_select(columns, statement)
            )


def refresh_derived_models(connection=None):
    """ Refresh all materialized views declared with db.Model. """
    def _refresh_models(c):
        for m in iter_models(DerivedModel):
            m.refresh(c)

    if connection is None:
        with db.engine.begin() as conn:
            _refresh_models(conn)
    else:
        _refresh_models(connection)


class _ValuesClause(sa.sql.FromClause):
    """ Represents a VALUES expression in a FROM clause. """
    named_with_column = True

    def __init__(self, columns, *args, alias_name=None, **kw):
        self._column_args = columns
        self.list = args
        self.alias_name = self.name = alias_name

    def _populate_column_collection(self):
        for column in self._column_args:
            column._make_proxy(self, column.name)


@sa_compiler.compiles(_ValuesClause)
def _compile_values(element, compiler, asfrom=False, **kw):
    """ Crates VALUES expression from list of columns and list of tuples. """

    def print_value(value, column):
        type_ = column.type if value is not None else db.NULLTYPE
        str_value = compiler.process(db.bindparam(None, value, type_=type_))

        return str_value + "::" + str(column.type)

    expression = "VALUES " + ", ".join(
        "(" + ", ".join(
            print_value(value, column)
            for value, column in zip(row, element.columns)
        ) + ")"
        for row in element.list
    )

    if asfrom and element.alias_name is not None:
        name = compiler.preparer.quote(element.alias_name)
        columns = ", ".join(column.name for column in element.columns)
        expression = f"({expression}) AS {name} ({columns})"
    elif asfrom:
        expression = "(" + expression + ")"

    return expression


def values(columns, *args, alias_name=None):
    """ Creates a VALUES expression for use in FROM clauses. """
    return _ValuesClause(columns, *args, alias_name=alias_name)
