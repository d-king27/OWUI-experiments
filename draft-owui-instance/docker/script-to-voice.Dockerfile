FROM python:3.12.12-slim-bookworm
WORKDIR /app
COPY pyproject.toml README.md uv.lock ./
COPY agent ./agent
RUN pip install --no-cache-dir uv==0.9.7 && uv sync --frozen --extra stv --no-dev
ENV PATH="/app/.venv/bin:$PATH" STV_DATA_ROOT=/data PYTHONUNBUFFERED=1
RUN mkdir /data && chown -R 10001:10001 /data /app
USER 10001:10001
CMD ["uvicorn", "script_to_voice.service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
