import os

from dotenv import load_dotenv


def _get_env_var(name, *, cast=None, default=None):
    value = os.environ.get(name)

    if not value:
        return default
    elif cast is None or cast is str:
        return value
    elif cast is bool:
        normalised = value.strip().lower()
        truthy = ("1", "true", "t")
        falsy = ("", "0", "false", "f")
        if normalised in truthy:
            return True
        elif normalised in falsy:
            return False
        else:
            raise ValueError(f"Expected string in {truthy + falsy!r}.")
    elif cast is int:
        return int(value)
    else:
        raise ValueError("Expected cast to 'str', 'bool' or 'int'.")


# Load environment variables from .env file
load_dotenv(".env")


class Config:
    """ The application config. """

    # Location of PostgreSQL database
    SQLALCHEMY_DATABASE_URI = _get_env_var("NXB_DATABASE_URI")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Must be kept False and let all SQLAlchemy queries be logged
    SQLALCHEMY_ECHO = False

    # Location of file to dump database to and restore from
    DATABASE_DUMP_PATH = _get_env_var("NXB_DATABASE_DUMP_PATH")
    # Temporary directory path for population
    TEMP_DIRECTORY = _get_env_var("NXB_TEMP_DIRECTORY")
    # Directory to place logs in
    LOG_DIRECTORY = _get_env_var("NXB_LOG_DIRECTORY", default=".")

    # A different secret key must be set in production
    SECRET_KEY = _get_env_var("NXB_SECRET_KEY")

    # Enables CSRF in WTForms objects
    WTF_CSRF_ENABLED = True

    # Time to expire if cookie is permanent (1 year)
    PERMANENT_SESSION_LIFETIME = 365 * 24 * 60 * 60
    # With permanent cookie, only update if necessary
    SESSION_REFRESH_EACH_REQUEST = False
    # Set same-site policy for cookies as 'Lax'.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Enables geolocation on webpages, which requires HTTPS
    GEOLOCATION_ENABLED = _get_env_var("NXB_GEOLOCATION_ENABLED", cast=bool, default=False)

    # Requests data from TAPI if true, else use timetabled data
    TRANSPORT_API_ACTIVE = _get_env_var("NXB_TAPI_ACTIVE", cast=bool, default=False)
    # Set a limit on the number of requests per day starting at 00:00 UTC
    # Further requests will utilise timetabled data. Ignored if negative or None
    TRANSPORT_API_LIMIT = _get_env_var("NXB_TAPI_LIMIT", cast=int)
    # ID for Transport API
    TRANSPORT_API_ID = _get_env_var("NXB_TAPI_ID")
    # Key for Transport API
    TRANSPORT_API_KEY = _get_env_var("NXB_TAPI_KEY")

    # FTP username and password for TNDS files
    TNDS_USERNAME = _get_env_var("NXB_TNDS_USERNAME")
    TNDS_PASSWORD = _get_env_var("NXB_TNDS_PASSWORD")
