"""
Database model extensions for the nextbus package.

SQLAlchemy materialized view code based on code from the following:
http://www.jeffwidman.com/blog/847/using-sqlalchemy-to-create-and-manage-postgresql-materialized-views/
https://bitbucket.org/zzzeek/sqlalchemy/wiki/UsageRecipes/Views
"""
import sqlalchemy as sa
import sqlalchemy.ext.compiler as sa_compiler

from nextbus import db


def table_name(model):
    """ Returns column with literal name of model table. """
    return db.literal_column("'%s'" % model.__tablename__)


class BaseModel(db.Model):
    """ Adds functionality to the Flask-SQLAlchemy model class. """
    __abstract__ = True
    __table__ = None

    def _asdict(self):
        """ Returns a dictionary of currently loaded columns in a model object.
            Any deferred columns or relationships will not be included.
        """
        return {attr: value for attr, value in self.__dict__.items()
                if attr in self.__table__.columns}


class _CreateMatView(sa.schema.DDLElement):
    """ Creates materialized view with a command. """
    def __init__(self, name, selectable, with_data=False):
        self.name = name
        self.selectable = selectable
        self.with_data = with_data


class _DropMatView(sa.schema.DDLElement):
    """ Drops materialized view with a command. """
    def __init__(self, name):
        self.name = name


class _RefreshMatView(sa.schema.DDLElement):
    """ Drops materialized view with a command. """
    def __init__(self, name, concurrently=False):
        self.name = name
        self.concurrently = concurrently


@sa_compiler.compiles(_CreateMatView)
def _compile_create_mat_view(clause, compiler):
    statement = "CREATE MATERIALIZED VIEW %s AS %s WITH %s"
    selectable = compiler.sql_compiler.process(clause.selectable,
                                               literal_binds=True)
    with_data = "DATA" if clause.with_data else "NO DATA"

    return statement % (clause.name, selectable, with_data)


@sa_compiler.compiles(_DropMatView)
def _compile_drop_mat_view(clause, _):
    return "DROP MATERIALIZED VIEW IF EXISTS " + clause.name


@sa_compiler.compiles(_RefreshMatView)
def _compile_refresh_mat_view(clause, _):
    statement = "REFRESH MATERIALIZED VIEW "
    if clause.concurrently:
        statement += "CONCURRENTLY "

    return statement + clause.name


def create_mat_view(name, selectable, metadata=db.metadata):
    """ Creates a table based on the materialized view selectable and adds
        events for ``db.create_all()`` and ``db.drop_all()``.

        :param name: Name of materialized view
        :param selectable: Query object
        :param metadata: Metadata object, by default it is the same as used by
        the application
        :returns: A ``Table`` object corresponding to the materialized view
    """
    # Separate metadata for this table, to avoid inclusion in db.create_all()
    _metadata = db.MetaData()
    table = db.Table(name, _metadata)

    # Add columns based on selectable
    for col in selectable.columns:
        column = db.Column(col.name, col.type, primary_key=col.primary_key)
        table.append_column(column)

    # Set view to be created and dropped at same time as metadata
    @db.event.listens_for(metadata, "after_create")
    def create_view(_, connection, **kw):
        connection.execute(_CreateMatView(name, selectable))
        # Add indexes after metadata created
        for idx in table.indexes:
            idx.create(connection)

    @db.event.listens_for(metadata, "before_drop")
    def drop_view(_, connection, **kw):
        connection.execute(_DropMatView(name))

    return table


class MaterializedView(BaseModel):
    """ ORM class for a materialized view. """
    __abstract__ = True

    @classmethod
    def refresh(cls, concurrently=False):
        """ Refreshes materialized view. Must be committed in a transaction. """
        db.session.flush()
        db.session.execute(_RefreshMatView(cls.__table__.fullname,
                                           concurrently))


def refresh_mat_views(concurrently=False):
    """ Refresh all materialized views declared with db.Model. """
    for m in db.Model._decl_class_registry.values():
        if hasattr(m, "__table__") and issubclass(m, MaterializedView):
            m.refresh(concurrently)


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
        expression = "(%s) AS %s (%s)" % (
            expression,
            element.alias_name,
            ", ".join(column.name for column in element.columns)
        )
    elif asfrom:
        expression = "(" + expression + ")"

    return expression


def values(columns, *args, alias_name=None):
    """ Creates a VALUES expression for use in FROM clauses. """
    return _ValuesClause(columns, *args, alias_name=alias_name)
