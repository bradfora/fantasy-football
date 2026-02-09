FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --progress-bar=off -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["flask", "run", "--host=0.0.0.0", "--port=8000"]
