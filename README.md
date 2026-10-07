# TDT4225-ex2

## Setup

```sh
cp .env.example .env
uv sync
uv run pre-commit install
docker compose up -d
```

The database connection settings are read from `.env`. Modify username and password in `.env` if wanted, before starting the database.

## Usage

```sh
uv run fill_db   # drop, recreate and fill the tables (asks first; --force to skip)
uv run task2     # run the task 2 queries
```

The exploratory data analysis is in `notebooks/eda.ipynb`. Open it in VS Code and select the `.venv` kernel.

## Pre-commit hooks

Install the hooks so they run before every commit:

```sh
uv run pre-commit install
```

Run the hooks over all files:

```sh
uv run pre-commit run --all-files
```
