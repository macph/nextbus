FROM python:3.9-slim-bullseye AS base

# Set poetry version
ENV POETRY_VERSION 1.1.12
ENV POETRY_VIRTUALENVS_IN_PROJECT 1
ENV PYTHONDONTWRITEBYTECODE 1

# Set up virtualenv for Poetry and install it
RUN python -m venv /poetry && /poetry/bin/pip3 install "poetry==$POETRY_VERSION"

WORKDIR /app
COPY . .

RUN /poetry/bin/poetry build -f sdist && rm -r /poetry

RUN python -m venv .venv && .venv/bin/pip3 install ./dist/*.tar.gz

# Set starting script as executable
RUN chmod +x ./populate.sh ./start.sh

FROM base as production
# Expose app through port 8000
EXPOSE 8000
CMD ["./start.sh"]

FROM base as test
RUN .venv/bin/pip3 install pytest
CMD [".venv/bin/pytest"]
