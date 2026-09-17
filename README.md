# TDT4225-ex2

## Setup

```sh
uv sync
docker compose up -d
```

## Pre-commit hooks

Install the hooks so they run before every commit:

```sh
uv run pre-commit install
```

Run the hooks over all files:

```sh
uv run pre-commit run --all-files
```
