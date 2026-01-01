# Flipke d'n Dappere

In 1386, the Brabantian Philip the Bold (Brabantian Dutch: Flipke d'n Dappere) established a Council Chamber in Lille for financial and legal matters concerning Flanders, Artois, Antwerp, and Mechlin. This regional body was a seed from which the States-General of the Netherlands would later grow.

Flipke is an API for network analysis and visualization of named entities in historical governance documents from the Low Countries.

- https://en.wikipedia.org/wiki/Philip_the_Bold
- https://en.wikipedia.org/wiki/States_General_of_the_Netherlands
- https://nl.wikipedia.org/wiki/Filips_de_Stoute
- https://nl.wikipedia.org/wiki/Staten-Generaal_van_de_Nederlanden

## Install Flipke

```bash
pip install -r requirements.txt
```

## Dowload, Install, and Start Docker (Desktop)

`https://www.docker.com/products/docker-desktop/`

## Start Services

```bash
docker-compose up -d
```

## Start Flipke API & Worker

**Important:** Start both the API and Worker for full functionality.

### Terminal 1 - API Server

```bash
python main.py
```

API will be available at: `http://localhost:8000/`

### Terminal 2 - Background Worker
```bash
python worker.py
```

Or use the batch file (Windows):
```bash
start_worker.bat
```

The worker processes download tasks from the RabbitMQ queue. Check `http://localhost:8000/queue/status` to verify the worker is connected (consumers should be > 0).

### Service URLs

### Queuing

`http://localhost:15672/#/queues/%2F/tasks`

Username/password: `admin/admin`

### Document Store

`http://localhost:8081/db/flipke_db/`

Username/password: `admin/admin`

### Graph Store

`http://localhost:7474/`

Username/password: `neo4j/password`

Query: `MATCH (n)-[r]->(m) RETURN n, r, m`

## Start Flipke

```bash
python main.py
```

`http://localhost:8000/`

## Stop Services

```bash
docker-compose down
```
