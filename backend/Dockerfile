FROM python:3.11-slim
WORKDIR /app
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
COPY data ./data
WORKDIR /app/backend
RUN pip install .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
