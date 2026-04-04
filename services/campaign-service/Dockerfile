FROM python:3.12-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY services/campaign-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/campaign-service/ /app/

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
