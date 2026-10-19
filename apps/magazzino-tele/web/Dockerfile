FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir Flask==3.1.1 mysql-connector-python==9.3.0 gunicorn==23.0.0
COPY app.py /app/app.py
RUN useradd -m -u 10001 tele
USER tele
EXPOSE 8082
CMD ["gunicorn","--workers","2","--bind","0.0.0.0:8082","--access-logfile","-","app:app"]
