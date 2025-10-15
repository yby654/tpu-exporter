FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    prometheus-client==0.19.0 \
    kubernetes==28.1.0 \
    google-cloud-container==2.35.0 \
    google-cloud-monitoring==2.16.0

COPY exporter.py /app/

EXPOSE 8000

CMD ["python", "-u", "exporter.py"]
