FROM python:3.11-slim

WORKDIR /timeseries_api
ENV PYTHONPATH="${PYTHONPATH}:/timeseries_api"

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY timeseries_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY timeseries_api/ .   
EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
