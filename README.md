# Flipke d'n Dappere

In 1386, the Brabantian Philip the Bold (Brabantian Dutch: Flipke d'n Dappere) established a Council Chamber in Lille for financial and legal matters concerning Flanders, Artois, Antwerp, and Mechlin. This regional body was a seed from which the States-General of the Netherlands would later grow.

Flipke is an API for network analysis and visualization of named entities in historical governance documents from the Low Countries.

- [Wikipedia: Philip the Bold](https://en.wikipedia.org/wiki/Philip_the_Bold)
- [Wikipedia: States-General of the Netherlands](https://en.wikipedia.org/wiki/States_General_of_the_Netherlands)
- [Wikipedia: Filips de Stoute (Dutch)](https://nl.wikipedia.org/wiki/Filips_de_Stoute)
- [Wikipedia: Staten-Generaal van de Nederlanden (Dutch)](https://nl.wikipedia.org/wiki/Staten-Generaal_van_de_Nederlanden)

## How Does This App Work?

This app visualizes the distribution of power in the Low Countries by measuring the eigenvector centrality of persons mentioned in the resolutions of the States-General and their (power) position in relation to others mentioned in the same documents.

1. The REPUBLIC project digitalized the handwritten resolutions of the States-General between 1576 and 1796.
2. The REPUBLIC project applied the NLP techniques OCR and NER to extract named entities from the texts.
3. I download the relevant datasets from steps (1) and (2).
4. I parse the personal named entities, the resolutions they are mentioned in, and their ambiguous textual names. The obtained entities and relations I store as nodes and vertices in a graph.
5. For every person, I count the number of other people that share resolutions in which both of them are mentioned.
6. For every person, I calculate the 'normalized eigenvector centrality score' that measures the centrality of the person in the graph -- a approximation measure of relative power.
7. The data is propagated to the visualization app.

The visualization app shows a year-by-year distribution of power with the most prominent statesmen at the top of the page. The size of the circle reflects the person's relative power position. By clicking on one of the circles one can highlight its position over time. At the top of the page the personal named entity is shown, together with all the ambiguous names that were found across the resolutions, a link with more information about the personal named entity (the P identifier), and the calculated normalized eigenvector centrality score. The years in red represent the years in which the Dutch Republic was at war. Click on the year (mobile) or the conflict bar (desktop) to find more information about the conflict.

From the third step onwards, this API provides the endpoints to replicate the process yourself.

- [Huygens Institute: Resoluties van de Staten-Generaal (Dutch)](https://www.huygens.knaw.nl/projecten/resoluties-staten-generaal-1576-1796-de-oerbronnen-van-de-parlementaire-democratie/)
- [Huygens Institute: Instrumenten van macht (Dutch)](https://resources.huygens.knaw.nl/retroboeken/instrumenten_macht/#view=homePane&page=0&accessor=toc)
- [Wikipedia: Optical character recognition (OCR)](https://en.wikipedia.org/wiki/Optical_character_recognition)
- [Huygens Institute: REPUBLIC PageXML ground truth handwritten resolutions States General](https://zenodo.org/records/7695131)
- [Wikipedia: Named-entity recognition (NER)](https://en.wikipedia.org/wiki/Named-entity_recognition)
- [Huygens Institute: Entities recognised in the resolutions of the States General of the Dutch Republic (1576-1796)](https://zenodo.org/records/15495712)
- [Goetgevonden (Dutch)](https://app.goetgevonden.nl/)
- [Wikipedia: Eigenvector centrality](https://en.wikipedia.org/wiki/Eigenvector_centrality)

## Install Flipke

```bash
pip install -r requirements.txt
```

## Dowload, Install, and Start Docker (Desktop)

[Docker Desktop](https://www.docker.com/products/docker-desktop/)

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

API will be available at: [localhost:8000](http://localhost:8000/)

### Terminal 2 - Background Worker

```bash
python worker.py
```

The worker processes messages from the RabbitMQ queue. Check [localhost:8000/queue/status](http://localhost:8000/queue/status) to verify the worker is connected (consumers should be > 0).

### Service URLs

### Queuing

[localhost:15672](http://localhost:15672/#/queues)

Username/password: `admin/admin`

### Document Store

[localhost:8081](http://localhost:8081/db/flipke_db/)

Username/password: `admin/admin`

### Graph Store

[localhost:7474](http://localhost:7474/)

Username/password: `neo4j/password`

Query: `MATCH (n)-[r]->(m) RETURN n, r, m`

## Start Flipke

```bash
python main.py
```

[localhost:8000](http://localhost:8000/)

## Stop Services

```bash
docker-compose down
```
