FROM python:3.8
WORKDIR /app
COPY requirements.txt .
RUN pip3 install -q -r requirements.txt
COPY btc.py config.yaml clients.py config.py db.py web.py ./
ENTRYPOINT ["python3", "btc.py"]
