FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock.txt ./
COPY voc ./voc
RUN pip install -c requirements.lock.txt . && useradd --create-home appuser
COPY app.py ./
COPY .streamlit ./.streamlit
COPY data/synthetic_feedback.csv ./data/synthetic_feedback.csv
RUN mkdir -p /app/storage && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000 8501
CMD ["uvicorn", "voc.api:app", "--host", "0.0.0.0", "--port", "8000"]
