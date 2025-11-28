
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/instance

ENV FLASK_APP=app.py
ENV FLASK_ENV=production

EXPOSE 5002

CMD ["python", "app.py"]
