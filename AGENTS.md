# Repository execution rules

- Use UV for every Python operation.
- Run project commands as `uv run python -m <module>`.
- Create and synchronize the environment with `uv sync`.
- Add or remove dependencies with `uv add` and `uv remove`.
- Never invoke `python`, `python3`, `pip`, or `.venv/bin/python` directly.
