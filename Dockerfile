FROM python:3.9-slim

WORKDIR /app

COPY distributed_drive/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variable to determine which script to run
ENV SERVICE_TYPE=master
ENV PORT=5000

CMD ["sh", "-c", "if [ \"$SERVICE_TYPE\" = \"master\" ]; then python distributed_drive/master_node/app.py; else python distributed_drive/storage_node/server.py $PORT; fi"]
