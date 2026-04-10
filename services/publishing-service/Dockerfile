FROM python:3.12-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY services/publishing-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/publishing-service/ /app/

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
