# ReDeFi XCM Viewer

Web application for viewing status of cross-chain transfers.

## Build and run

## Production

Use [docker-compose.yml](docker/docker-compose.yml).

## Debug

1. Copy .template.env to .venv: `cp .template.env .env`.
2. Change urls in .env.
3. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
   
   Note: You can use pyenv or any other utilities, the requirements.txt file is included. However, the following steps assume that uv is installed.
4. Run `uv run app.py`.

## Screenshots

[Screenshot](./screenshot.png)