FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install boto3 prometheus_client ipaddress

CMD ["python", "main.py"]
