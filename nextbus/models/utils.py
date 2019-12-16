"""
Database model extensions for the nextbus package.
"""
from abc import abstractmethod

import sqlalchemy as sa
import sqlalchemy.ext.compiler as sa_compiler

from nextbus import db


def table_name(model):
    """ Returns column with literal name of model table. """
    return db.literal_column(f"'{model.__tablename__}'")


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
        for m in db.Model._decl_class_registry.values():
            if hasattr(m, "__table__") and issubclass(m, DerivedModel):
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
