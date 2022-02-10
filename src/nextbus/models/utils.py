"""
Database model extensions for the nextbus package.
"""
import sqlalchemy.exc

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


class _ModelData:
    """ Holds a collection of registered model data handlers. """
    def __init__(self):
        self._models = []
        self._columns = []

    def register_model(self, model):
        """ Register a handler for refreshing rows for a table from selectables.
        """
        def register(func):
            logger.debug(f"Registering handler for model {model!r}")
            self._models.append((model, func))
            return func

        return register

    def register_columns(self, model, *columns):
        """ Register a handler for refreshing columns for in a table.
        """
        if not columns:
            raise ValueError("At least one column expected")

        set_columns = set(columns)
        existing = {c.name for c in model.__table__.columns}
        keys = {k.name for k in model.__table__.primary_key}

        if set_columns - existing:
            raise ValueError(f"Columns {columns!r} must match model {model}")
        if set_columns & keys:
            raise ValueError("Primary keys cannot be used for data generation")

        def register(func):
            logger.debug(
                f"Registering handler for model {model!r} and columns "
                f"{set_columns!r}"
            )
            self._columns.append((model, keys, set_columns, func))
            pass

        return register

    def refresh(self, connection):
        """ Refresh all registered models and columns. """
        for model, func in self._models:
            columns = [c.key for c in model.__table__.columns]

            logger.debug(f"Deleting all rows for model {model!r}")
            connection.execute(model.__table__.delete())

            for statement in func(connection):
                logger.info(f"Inserting rows for model {model!r}")
                connection.execute(
                    model.__table__.insert().from_select(columns, statement)
                )

        for model, keys, columns, func in self._columns:
            table = model.__table__
            for inner in func(connection):
                logger.info(f"Updating columns {columns!r} for model {model!r}")
                values = {c: inner.columns[c] for c in columns}
                where = db.and_(*(table.c[k] == inner.c[k] for k in keys))
                connection.execute(table.update().values(**values).where(where))


data = _ModelData()
