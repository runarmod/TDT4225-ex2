# TDT4225-ex2

## Setup

```sh
cp .env.example .env
uv sync
docker compose up -d
```

The database connection settings are read from `.env`. Modify username and password in `.env` if wanted, before starting the database.

## Pre-commit hooks

Install the hooks so they run before every commit:

```sh
uv run pre-commit install
```

Run the hooks over all files:

```sh
uv run pre-commit run --all-files
```
