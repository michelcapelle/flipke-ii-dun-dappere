import pika
import json
import httpx
from pathlib import Path
import time
import sys
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import logging
from neo4j import GraphDatabase
import zipfile
import gzip
import shutil
from bs4 import BeautifulSoup
import networkx as nx
from networkx.algorithms import bipartite

data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(data_dir / 'worker.log')
    ]
)
logger = logging.getLogger(__name__)
mongo_client = MongoClient('mongodb://admin:admin@localhost:27017/')
db = mongo_client['flipke_db']
tasks_collection = db['tasks']
documents_collection = db['documents']
person_analysis_collection = db['person_analysis']
person_names_collection = db['person_names']
neo4j_driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password")
)

def update_task_status(task_id, status, message, progress=None, **kwargs):
    update_data = {
        "status": status,
        "message": message,
        "updated_at": datetime.now()
    }
    if progress is not None:
        update_data["progress"] = progress
    update_data.update(kwargs)
    tasks_collection.update_one(
        {"_id": ObjectId(task_id)},
        {"$set": update_data}
    )

def trigger_next_pipeline_step(message_data):
    pipeline_task_id = message_data.get('pipeline_task_id')
    next_step = message_data.get('next_step')
    pipeline_year = message_data.get('pipeline_year')
    current_step = message_data.get('pipeline_step')
    if not pipeline_task_id or not next_step:
        return
    from pathlib import Path
    worker_dir = Path(__file__).parent
    analysis_file = worker_dir / "flipke-iii-dun-broave" / "public" / "analysis" / f"{pipeline_year}.json"
    if analysis_file.exists():
        logger.info(f"Analysis file for year {pipeline_year} already exists at {analysis_file}. Stopping pipeline.")
        tasks_collection.update_one(
            {"_id": ObjectId(pipeline_task_id)},
            {"$set": {
                f"steps.{current_step}.status": "completed",
                "status": "completed",
                "progress": 100,
                "message": f"Step {current_step} completed. Analysis file already exists, pipeline stopped.",
                "completed_at": datetime.now(),
                "updated_at": datetime.now()
            }}
        )
        return
    
    logger.info(f"Triggering next pipeline step: {next_step} for pipeline {pipeline_task_id}")
    progress_map = {
        "clear_graph": 20,
        "parse_entities": 40,
        "analyze_persons": 60,
        "calculate_centrality": 80,
        "export_analysis": 100
    }
    
    tasks_collection.update_one(
        {"_id": ObjectId(pipeline_task_id)},
        {"$set": {
            f"steps.{current_step}.status": "completed",
            f"steps.{next_step}.status": "running",
            "current_step": next_step,
            "progress": progress_map.get(current_step, 0),
            "message": f"Step {current_step} completed, starting {next_step}",
            "updated_at": datetime.now()
        }}
    )
    step_sequence = {
        "parse_entities": "analyze_persons",
        "analyze_persons": "calculate_centrality",
        "calculate_centrality": "export_analysis",
        "export_analysis": None
    }
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='localhost',
            port=5672,
            credentials=pika.PlainCredentials('admin', 'admin')
        )
    )
    channel = connection.channel()
    channel.queue_declare(queue='tasks', durable=True)
    
    next_message = {
        "pipeline_task_id": pipeline_task_id,
        "pipeline_year": pipeline_year,
        "pipeline_step": next_step,
        "next_step": step_sequence.get(next_step),
        "timestamp": datetime.now().isoformat()
    }
    
    if next_step == "parse_entities":
        next_message["task"] = "pre_modern_parse_entities"
        next_message["year"] = pipeline_year
    elif next_step == "analyze_persons":
        next_message["task"] = "pipeline_analyze_persons"
        next_message["year"] = pipeline_year
    elif next_step == "calculate_centrality":
        next_message["task"] = "calculate_eigenvector_centrality"
        next_message["year"] = pipeline_year
    elif next_step == "export_analysis":
        next_message["task"] = "export_analysis"
        next_message["year"] = pipeline_year
    channel.basic_publish(
        exchange='',
        routing_key='tasks',
        body=json.dumps(next_message),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    connection.close()
    
    logger.info(f"Queued next step: {next_step}")

def pre_modern_download(message_data):
    url = message_data['url']
    filename = message_data['filename']
    do_force = message_data['doForce']
    task_id = message_data.get('task_id')
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    file_path = data_dir / filename
    if file_path.exists() and not do_force:
        logger.info(f"File {filename} already exists. Skipping download. (use doForce=true to force)")
        if task_id:
            update_task_status(
                task_id,
                status="skipped",
                message="File already exists",
                progress=100,
                file=str(file_path)
            )
        return {
            "status": "skipped",
            "message": "File already exists",
            "file": str(file_path)
        }  
    try:
        if task_id:
            update_task_status(
                task_id,
                status="downloading",
                message=f"Downloading from {url}",
                progress=10
            )
        logger.info(f"Downloading from {url}...")
        logger.info(f"Target file: {file_path}")
        downloaded_bytes = 0
        chunk_size = 1024 * 1024
        with httpx.Client(timeout=3600.0) as client:
            with client.stream('GET', url, follow_redirects=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                logger.info(f"Total size: {total_size / (1024**3):.2f} GB" if total_size else "Total size: unknown")
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        if downloaded_bytes % (100 * 1024 * 1024) < chunk_size:
                            progress_mb = downloaded_bytes / (1024**2)
                            logger.info(f"Downloaded: {progress_mb:.0f} MB")
                            if task_id and total_size > 0:
                                download_progress = int((downloaded_bytes / total_size) * 50) + 10
                                update_task_status(
                                    task_id,
                                    status="downloading",
                                    message=f"Downloading: {progress_mb:.0f} MB / {total_size/(1024**2):.0f} MB",
                                    progress=min(download_progress, 60)
                                )
        logger.info(f"Download completed: {file_path.stat().st_size} bytes ({file_path.stat().st_size / (1024**3):.2f} GB)")
        extracted_file = None
        if filename.endswith('.gz'):
            if task_id:
                update_task_status(
                    task_id,
                    status="extracting",
                    message="Extracting compressed file",
                    progress=70
                )
            logger.info(f"Extracting .gz file: {file_path}")
            extracted_file = data_dir / filename[:-3]
            try:
                with gzip.open(file_path, 'rb') as f_in:
                    with open(extracted_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                logger.info(f"Extraction completed: {extracted_file}")
                if task_id:
                    update_task_status(
                        task_id,
                        status="extracting",
                        message="Extraction completed",
                        progress=90
                    )
            except Exception as e:
                logger.error(f"Error extracting .gz file: {str(e)}", exc_info=True)
                if task_id:
                    update_task_status(
                        task_id,
                        status="failed",
                        message=f"Extraction error: {str(e)}",
                        progress=70,
                        error=str(e)
                    )
                return {
                    "status": "error",
                    "message": f"Extraction failed: {str(e)}"
                }
        
        if task_id:
            status_data = {
                "downloaded_file": str(file_path),
                "download_size_bytes": file_path.stat().st_size,
            }
            if extracted_file:
                status_data["extracted_file"] = str(extracted_file)
                status_data["extracted_size_bytes"] = extracted_file.stat().st_size
            
            update_task_status(
                task_id,
                status="completed",
                message="Download and extraction completed successfully",
                progress=100,
                completed_at=datetime.now(),
                **status_data
            )        
        
        result = {
            "status": "success",
            "downloaded_file": str(file_path),
            "download_size_bytes": file_path.stat().st_size,
        }
        if extracted_file:
            result["extracted_file"] = str(extracted_file)
            result["extracted_size_bytes"] = extracted_file.stat().st_size
        
        return result
    except Exception as e:
        logger.error(f"Error during download/extract: {str(e)}", exc_info=True)
        if task_id:
            update_task_status(
                task_id,
                status="failed",
                message=f"Error: {str(e)}",
                progress=0,
                error=str(e)
            )        
        return {
            "status": "error",
            "message": str(e)
        }

def pre_modern_parse_entity(message_data):
    annotation = message_data.get('annotation')
    master_task_id = message_data.get('master_task_id')
    annotation_index = message_data.get('annotation_index', 0)
    total_annotations = message_data.get('total_annotations', 0)
    filter_year = message_data.get('filter_year')
    if not annotation:
        logger.error("No annotation data provided")
        return {"status": "error", "message": "No annotation data"}
    try:
        person_id = annotation.get('entity')
        reference = annotation.get('reference', {})
        if not person_id or not reference:
            logger.warning(f"Incomplete annotation at index {annotation_index}")
            return {"status": "skipped", "message": "Incomplete annotation"}
        document_id = reference.get('resolution_id')
        if filter_year is not None:
            if not document_id:
                return {"status": "skipped", "message": "No resolution_id for year filtering"}
            global _year_resolution_cache
            cache_key = f"year_{filter_year}"
            if cache_key not in _year_resolution_cache:
                tsv_file = Path("data/republic-paragraphs-2025-02-20.tsv")
                if not tsv_file.exists():
                    logger.error(f"TSV file not found for year filtering: {tsv_file}")
                    return {"status": "error", "message": "TSV file not found for year filtering"}
                
                logger.info(f"Loading resolution_ids for year {filter_year} into cache...")
                year_resolutions = set()
                year_prefix = f"{filter_year}-"
                with open(tsv_file, 'r', encoding='utf-8') as f:
                    next(f)
                    for line in f:
                        parts = line.strip().split('\t')
                        if len(parts) >= 2:
                            session_date = parts[0]
                            resolution_id = parts[1]
                            if session_date.startswith(year_prefix):
                                year_resolutions.add(resolution_id)
                
                _year_resolution_cache[cache_key] = year_resolutions
                logger.info(f"Cached {len(year_resolutions)} resolution_ids for year {filter_year}")
            if document_id not in _year_resolution_cache[cache_key]:
                return {"status": "skipped", "message": f"Resolution {document_id} not in year {filter_year}"}
        
        name = reference.get('tag_text', '')
        
        with neo4j_driver.session() as session:
            if document_id and name:
                session.run("""
                    MERGE (p:Person {id: $person_id})
                    MERGE (d:Document {id: $document_id})
                    MERGE (n:Name {name: $name})
                    MERGE (p)-[:MENTIONED_IN]->(d)
                    MERGE (p)-[:HAS_NAME]->(n)
                """, person_id=person_id, document_id=document_id, name=name)
            elif document_id:
                session.run("""
                    MERGE (p:Person {id: $person_id})
                    MERGE (d:Document {id: $document_id})
                    MERGE (p)-[:MENTIONED_IN]->(d)
                """, person_id=person_id, document_id=document_id)
            elif name:
                session.run("""
                    MERGE (p:Person {id: $person_id})
                    MERGE (n:Name {name: $name})
                    MERGE (p)-[:HAS_NAME]->(n)
                """, person_id=person_id, name=name)
            else:
                session.run("""
                    MERGE (p:Person {id: $person_id})
                """, person_id=person_id)
        
        if master_task_id and (annotation_index + 1) % 1000 == 0:
            progress = int(((annotation_index + 1) / total_annotations) * 100)
            tasks_collection.update_one(
                {"_id": ObjectId(master_task_id)},
                {"$set": {
                    "status": "processing",
                    "progress": progress,
                    "message": f"Processed {annotation_index + 1}/{total_annotations} annotations",
                    "updated_at": datetime.now()
                }}
            )
            logger.info(f"Progress: {annotation_index + 1}/{total_annotations} ({progress}%)")
        if master_task_id:
            result = tasks_collection.find_one_and_update(
                {"_id": ObjectId(master_task_id)},
                {
                    "$inc": {"processed": 1},
                    "$set": {"updated_at": datetime.now()}
                },
                return_document=True
            )
            if result and result.get("processed", 0) >= result.get("total", 0):
                tasks_collection.update_one(
                    {"_id": ObjectId(master_task_id)},
                    {"$set": {
                        "status": "completed",
                        "progress": 100,
                        "message": f"All {result.get('total', 0)} annotations processed successfully",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }}
                )
                logger.info(f"Completed processing all {result.get('total', 0)} annotations")
                if result.get('pipeline_task_id') and result.get('next_step'):
                    pipeline_message = {
                        'pipeline_task_id': result.get('pipeline_task_id'),
                        'pipeline_year': result.get('pipeline_year'),
                        'pipeline_step': 'parse_entities',
                        'next_step': result.get('next_step')
                    }
                    trigger_next_pipeline_step(pipeline_message)
        
        return {
            "status": "success",
            "person_id": person_id,
        }
    except Exception as e:
        logger.error(f"Error parsing annotation at index {annotation_index}: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }

def analyze_person_connections(message_data):
    """
    Analyze a person's connections and store results in MongoDB.
    """
    person_id = message_data.get('person_id')
    master_task_id = message_data.get('master_task_id')
    person_index = message_data.get('person_index', 0)
    total_persons = message_data.get('total_persons', 0)
    year = message_data.get('year')
    
    if not person_id:
        logger.error("No person_id provided")
        return {"status": "error", "message": "No person_id provided"}
    
    try:
        with neo4j_driver.session() as session:
            connections_result = session.run("""
                MATCH (p:Person {id: $person_id})-[:MENTIONED_IN]->(d:Document)<-[:MENTIONED_IN]-(c:Person)
                WHERE p.id <> c.id
                RETURN COUNT(DISTINCT c) as connection_count
            """, person_id=person_id)
            connection_count = connections_result.single()["connection_count"]
            names_result = session.run("""
                MATCH (p:Person {id: $person_id})-[:HAS_NAME]->(n:Name)
                RETURN n.name as name
            """, person_id=person_id)
            names = [record["name"] for record in names_result]
        analysis_data = {
            "person_id": person_id,
            "connection_count": connection_count,
            "year": year,
            "analyzed_at": datetime.now()
        }
        person_analysis_collection.update_one(
            {"person_id": person_id, "year": year},
            {"$set": analysis_data},
            upsert=True
        )
        for name in names:
            name_data = {
                "person_id": person_id,
                "name": name,
                "year": year,
                "created_at": datetime.now()
            }
            person_names_collection.update_one(
                {"person_id": person_id, "name": name, "year": year},
                {"$set": name_data},
                upsert=True
            )
        if master_task_id and (person_index + 1) % 100 == 0:
            progress = int(((person_index + 1) / total_persons) * 100)
            tasks_collection.update_one(
                {"_id": ObjectId(master_task_id)},
                {"$set": {
                    "status": "processing",
                    "progress": progress,
                    "message": f"Analyzed {person_index + 1}/{total_persons} persons",
                    "updated_at": datetime.now()
                }}
            )
            logger.info(f"Progress: {person_index + 1}/{total_persons} ({progress}%)")
        if master_task_id:
            result = tasks_collection.find_one_and_update(
                {"_id": ObjectId(master_task_id)},
                {
                    "$inc": {"processed_count": 1},
                    "$set": {"updated_at": datetime.now()}
                },
                return_document=True
            )
            if result and result.get("processed_count", 0) >= result.get("total_persons", 0):
                tasks_collection.update_one(
                    {"_id": ObjectId(master_task_id)},
                    {"$set": {
                        "status": "completed",
                        "progress": 100,
                        "message": f"All {result.get('total_persons', 0)} persons analyzed successfully",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }}
                )
                logger.info(f"Completed analyzing all {result.get('total_persons', 0)} persons")
                if result.get('pipeline_task_id') and result.get('next_step'):
                    pipeline_message = {
                        'pipeline_task_id': result.get('pipeline_task_id'),
                        'pipeline_year': result.get('pipeline_year'),
                        'pipeline_step': 'analyze_persons',
                        'next_step': result.get('next_step')
                    }
                    trigger_next_pipeline_step(pipeline_message)
        
        return {
            "status": "success",
            "person_id": person_id,
            "connection_count": connection_count,
            "names_count": len(names)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing person {person_id}: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }

def pre_modern_parse_document(message_data):
    session_date = message_data.get('session_date')
    resolution_id = message_data.get('resolution_id')
    row_index = message_data.get('row_index', 0)
    total_rows = message_data.get('total_rows', 0)
    master_task_id = message_data.get('master_task_id')
    
    if not session_date or not resolution_id:
        logger.warning(f"Incomplete document data at row {row_index}")
        return {"status": "skipped", "message": "Incomplete document data"}
    try:
        document_data = {
            "resolution_id": resolution_id,
            "session_date": session_date
        }
        documents_collection.update_one(
            {"resolution_id": resolution_id, "session_date": session_date},
            {"$set": document_data},
            upsert=True
        )
        
        if master_task_id and (row_index + 1) % 1000 == 0:
            progress = int(((row_index + 1) / total_rows) * 100)
            tasks_collection.update_one(
                {"_id": ObjectId(master_task_id)},
                {"$set": {
                    "status": "processing",
                    "progress": progress,
                    "message": f"Processed {row_index + 1}/{total_rows} document rows",
                    "updated_at": datetime.now()
                }}
            )
            logger.info(f"Progress: {row_index + 1}/{total_rows} ({progress}%)")
        return {
            "status": "success",
            "resolution_id": resolution_id,
            "session_date": session_date
        }
    except Exception as e:
        logger.error(f"Error parsing document at row {row_index}: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }

def post_modern_scrape_page(message_data):
    url = message_data.get('url')
    task_id = message_data.get('task_id')
    do_force = message_data.get('doForce', False)
    try:
        logger.info(f"Scraping page: {url}")
        if task_id:
            update_task_status(
                task_id,
                status="scraping",
                message=f"Scraping page: {url}",
                progress=10
            )
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        browse_list = soup.find('ul', class_='browse__list')
        if not browse_list:
            logger.warning(f"No browse__list found on {url}")
            return {"status": "skipped", "message": "No browse__list found"}
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='tasks', durable=True)
        queued_documents = 0
        for li in browse_list.find_all('li'):
            a_tag = li.find('a')
            if a_tag and a_tag.get('href'):
                doc_url = a_tag.get('href')
                if not doc_url.startswith('http'):
                    doc_url = f"https://repository.overheid.nl{doc_url}"
                message = {
                    "task": "post_modern_download_document",
                    "url": doc_url,
                    "timestamp": datetime.now().isoformat()
                }
                channel.basic_publish(
                    exchange='',
                    routing_key='tasks',
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                queued_documents += 1
        logger.info(f"Queued {queued_documents} document links from {url}")
        pagination_div = soup.find('div', class_='pagination__index')
        if pagination_div:
            ul = pagination_div.find('ul')
            if ul:
                active_li = ul.find('li', class_='active')
                if active_li:
                    next_li = active_li.find_next_sibling('li')
                    if next_li:
                        a_tag = next_li.find('a')
                        if a_tag and a_tag.get('href'):
                            next_url = a_tag.get('href')
                            if not next_url.startswith('http'):
                                current_base_url = url.rsplit('?', 1)[0]
                                next_url = f"{current_base_url}{next_url}"
                            message = {
                                "task": "post_modern_scrape_page",
                                "url": next_url,
                                "doForce": do_force,
                                "timestamp": datetime.now().isoformat()
                            }
                            channel.basic_publish(
                                exchange='',
                                routing_key='tasks',
                                body=json.dumps(message),
                                properties=pika.BasicProperties(delivery_mode=2)
                            )
                            logger.info(f"Queued next page: {next_url}")
        connection.close()
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message=f"Scraped page, queued {queued_documents} documents",
                progress=50
            )
        return {
            "status": "success",
            "url": url,
            "queued_documents": queued_documents
        }
    except Exception as e:
        logger.error(f"Error scraping page {url}: {str(e)}", exc_info=True)
        if task_id:
            update_task_status(
                task_id,
                status="failed",
                message=f"Error: {str(e)}",
                error=str(e)
            )
        return {"status": "error", "message": str(e)}

def post_modern_download_document(message_data):
    url = message_data.get('url')
    try:
        logger.info(f"Downloading document page: {url}")
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            html_content = response.text        
        soup = BeautifulSoup(html_content, 'html.parser')
        sources_list = soup.find('ul', class_='list--sources')
        if not sources_list:
            logger.warning(f"No list--sources found on {url}")
            return {"status": "skipped", "message": "No sources found"}
        post_modern_dir = Path("data/post-modern")
        post_modern_dir.mkdir(parents=True, exist_ok=True)    
        downloaded_files = []
        for li in sources_list.find_all('li'):
            a_tag = li.find('a')
            if a_tag and a_tag.get('href'):
                file_url = a_tag.get('href')
                if not file_url.startswith('http'):
                    file_url = f"https://repository.overheid.nl{file_url}"
                filename = file_url.split('/')[-1].split('?')[0]
                if not filename:
                    filename = f"document_{hash(file_url)}"
                file_path = post_modern_dir / filename
                try:
                    with httpx.Client(timeout=60.0) as client:
                        with client.stream('GET', file_url, follow_redirects=True) as file_response:
                            file_response.raise_for_status()
                            with open(file_path, 'wb') as f:
                                for chunk in file_response.iter_bytes(chunk_size=1024*1024):
                                    f.write(chunk)    
                    logger.info(f"Downloaded: {filename}")
                    downloaded_files.append(str(file_path))
                except Exception as e:
                    logger.error(f"Error downloading {file_url}: {str(e)}")
        return {
            "status": "success",
            "url": url,
            "downloaded_files": downloaded_files,
            "count": len(downloaded_files)
        }
    except Exception as e:
        logger.error(f"Error downloading document {url}: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

def maintenance_purge_queues(message_data):
    """Purge only the 'tasks' queue, not the 'maintenance' queue"""
    task_id = message_data.get('task_id')
    try:
        logger.info("Purging tasks queue...")
        
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message="Purging queue",
                progress=10
            )
        
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        
        try:
            result = channel.queue_purge(queue='tasks')
            purged_count = result.method.message_count
        except pika.exceptions.ChannelClosedByBroker:
            purged_count = 0
        
        connection.close()
        
        logger.info(f"Purged {purged_count} message(s) from tasks queue")
        
        if task_id:
            update_task_status(
                task_id,
                status="completed",
                message=f"Purged {purged_count} message(s) from tasks queue",
                progress=100,
                total_purged=purged_count,
                completed_at=datetime.now()
            )
        
        return {
            "status": "success",
            "total_purged": purged_count
        }
        
    except Exception as e:
        logger.error(f"Error purging queue: {str(e)}", exc_info=True)
        if task_id:
            update_task_status(
                task_id,
                status="failed",
                message=f"Error: {str(e)}",
                error=str(e)
            )
        return {"status": "error", "message": str(e)}

def maintenance_delete_tasks(message_data):
    """
    Delete all task documents from MongoDB.
    """
    task_id = message_data.get('task_id')
    try:
        logger.info("Deleting all tasks...")
        
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message="Deleting tasks",
                progress=10
            )
        count_before = tasks_collection.count_documents({"_id": {"$ne": ObjectId(task_id)}}) if task_id else tasks_collection.count_documents({})
        if task_id:
            result = tasks_collection.delete_many({"_id": {"$ne": ObjectId(task_id)}})
        else:
            result = tasks_collection.delete_many({})
        
        deleted_count = result.deleted_count
        logger.info(f"Deleted {deleted_count} task document(s)")
        
        if task_id:
            update_task_status(
                task_id,
                status="completed",
                message=f"Deleted {deleted_count} task document(s) from MongoDB",
                progress=100,
                deleted_count=deleted_count,
                completed_at=datetime.now()
            )
        
        return {
            "status": "success",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error deleting tasks: {str(e)}", exc_info=True)
        if task_id:
            update_task_status(
                task_id,
                status="failed",
                message=f"Error: {str(e)}",
                error=str(e)
            )
        return {"status": "error", "message": str(e)}

def maintenance_delete_documents(message_data):
    task_id = message_data.get('task_id')
    try:
        logger.info("Deleting all documents...")    
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message="Deleting documents",
                progress=10
            )
        document_count = documents_collection.count_documents({})
        logger.info(f"Found {document_count} document(s) to delete")
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message=f"Deleting {document_count} document(s)",
                progress=30
            )
        delete_result = documents_collection.delete_many({})
        deleted_count = delete_result.deleted_count
        logger.info(f"Deleted {deleted_count} document(s)")
        if task_id:
            update_task_status(
                task_id,
                status="completed",
                message=f"Deleted {deleted_count} document(s) from MongoDB",
                progress=100,
                deleted_count=deleted_count,
                completed_at=datetime.now()
            )
        return {
            "status": "success",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error deleting documents: {str(e)}", exc_info=True)
        if task_id:
            update_task_status(
                task_id,
                status="failed",
                message=f"Error: {str(e)}",
                error=str(e)
            )
        return {"status": "error", "message": str(e)}

def maintenance_clear_graph(message_data):
    task_id = message_data.get('task_id')
    try:
        logger.info("Clearing Neo4j graph...")    
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message="Clearing graph",
                progress=10
            )
        with neo4j_driver.session() as session:
            count_result = session.run("""
                MATCH (n)
                RETURN count(n) as node_count
            """)
            initial_node_count = count_result.single()["node_count"]
            rel_count_result = session.run("""
                MATCH ()-[r]->()
                RETURN count(r) as rel_count
            """)
            initial_rel_count = rel_count_result.single()["rel_count"]
            logger.info(f"Found {initial_node_count} nodes and {initial_rel_count} relationships to delete")
            
            if task_id:
                update_task_status(
                    task_id,
                    status="processing",
                    message=f"Deleting {initial_node_count} nodes and {initial_rel_count} relationships in batches",
                    progress=20
                )
            batch_size = 1000
            total_deleted = 0
            batch_num = 0
            while True:
                result = session.run("""
                    MATCH (n)
                    WITH n LIMIT $batch_size
                    DETACH DELETE n
                    RETURN count(n) as deleted
                """, batch_size=batch_size)
                deleted_in_batch = result.single()["deleted"]
                if deleted_in_batch == 0:
                    break
                total_deleted += deleted_in_batch
                batch_num += 1
                if initial_node_count > 0:
                    progress = 20 + int((total_deleted / initial_node_count) * 70)
                else:
                    progress = 90
                logger.info(f"Batch {batch_num}: Deleted {deleted_in_batch} nodes (total: {total_deleted}/{initial_node_count})")
                if task_id:
                    update_task_status(
                        task_id,
                        status="processing",
                        message=f"Deleted {total_deleted}/{initial_node_count} nodes in {batch_num} batch(es)",
                        progress=min(progress, 90)
                    )       
        logger.info(f"Graph cleared successfully - deleted {total_deleted} nodes")
        if task_id:
            update_task_status(
                task_id,
                status="completed",
                message=f"Deleted {total_deleted} node(s) and {initial_rel_count} relationship(s) from Neo4j in {batch_num} batch(es)",
                progress=100,
                nodes_deleted=total_deleted,
                relationships_deleted=initial_rel_count,
                batches=batch_num,
                completed_at=datetime.now()
            )
        trigger_next_pipeline_step(message_data)
        return {
            "status": "success",
            "nodes_deleted": total_deleted,
            "relationships_deleted": initial_rel_count,
            "batches": batch_num
        }
    except Exception as e:
        logger.error(f"Error clearing graph: {str(e)}", exc_info=True)
        if task_id:
            update_task_status(
                task_id,
                status="failed",
                message=f"Error: {str(e)}",
                error=str(e)
            )
        return {"status": "error", "message": str(e)}

def calculate_eigenvector_centrality(message_data):
    """
    Calculate eigenvector centrality for persons in a specific year and update MongoDB.
    Uses NetworkX for calculation instead of Neo4j GDS.
    """
    task_id = message_data.get('task_id')
    year = message_data.get('year')
    
    if not year:
        logger.error("No year provided for centrality calculation")
        return {"status": "error", "message": "No year provided"}
    
    try:
        logger.info(f"Calculating eigenvector centrality for year {year}...")
        person_docs = list(person_analysis_collection.find(
            {"year": year},
            {"person_id": 1, "_id": 0}
        ))
        person_ids = [doc["person_id"] for doc in person_docs]
        
        if not person_ids:
            logger.info(f"No persons found for year {year}, completing step")
            if task_id:
                update_task_status(
                    task_id,
                    status="completed",
                    message=f"No persons found for year {year}, skipping centrality calculation",
                    progress=100,
                    completed_at=datetime.now()
                )
            pipeline_task_id = message_data.get('pipeline_task_id')
            if pipeline_task_id:
                next_step = message_data.get('next_step')
                if next_step:
                    trigger_next_pipeline_step(message_data)
                else:
                    pipeline_year = message_data.get('pipeline_year')
                    tasks_collection.update_one(
                        {"_id": ObjectId(pipeline_task_id)},
                        {"$set": {
                            "status": "completed",
                            "progress": 100,
                            "current_step": "completed",
                            f"steps.calculate_centrality.status": "completed",
                            "message": f"Pipeline completed successfully for year {pipeline_year} (no persons to calculate centrality for)",
                            "completed_at": datetime.now(),
                            "updated_at": datetime.now()
                        }}
                    )
                    logger.info(f"Pipeline {pipeline_task_id} completed for year {pipeline_year}")
            
            return {"status": "success", "message": f"No persons found for year {year}", "persons_updated": 0}
        
        logger.info(f"Found {len(person_ids)} persons for year {year}")    
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message=f"Building network graph for {len(person_ids)} persons from year {year}",
                progress=10
            )
        G = nx.Graph()        
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:MENTIONED_IN]->(d:Document)
                WHERE p.id IN $person_ids
                RETURN p.id AS person_id, d.id AS document_id
            """, person_ids=person_ids)
            for record in result:
                person_id = record["person_id"]
                document_id = record["document_id"]
                G.add_node(person_id, bipartite=0)
                G.add_node(document_id, bipartite=1)
                G.add_edge(person_id, document_id)
        logger.info(f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message=f"Calculating eigenvector centrality for year {year}",
                progress=40
            )
        try:
            centrality_scores = nx.eigenvector_centrality(G, max_iter=1000)
            centrality_scores = {node: score for node, score in centrality_scores.items() if node in person_ids}
            logger.info(f"Calculated centrality for {len(centrality_scores)} persons")
        except nx.PowerIterationFailedConvergence:
            logger.warning("Eigenvector centrality failed to converge, using degree centrality as fallback")
            centrality_scores = nx.degree_centrality(G)
            centrality_scores = {node: score for node, score in centrality_scores.items() if node in person_ids}
        if task_id:
            update_task_status(
                task_id,
                status="processing",
                message=f"Updating MongoDB with {len(centrality_scores)} centrality scores",
                progress=60
            )
        updated_count = 0
        for person_id, score in centrality_scores.items():
            result = person_analysis_collection.update_many(
                {"person_id": person_id, "year": year},
                {"$set": {
                    "eigenvector_centrality": score,
                    "centrality_updated_at": datetime.now()
                }}
            )
            updated_count += result.modified_count
            if updated_count % 1000 == 0:
                progress = 60 + int((updated_count / len(centrality_scores)) * 30)
                logger.info(f"Updated {updated_count}/{len(centrality_scores)} records for year {year}")
                if task_id:
                        update_task_status(
                            task_id,
                            status="processing",
                            message=f"Updated {updated_count}/{len(centrality_scores)} records for year {year}",
                            progress=progress
                        )
        logger.info(f"Successfully updated {updated_count} person records with centrality scores for year {year}")
        if task_id:
            update_task_status(
                task_id,
                status="completed",
                message=f"Calculated and stored eigenvector centrality for {updated_count} persons in year {year}",
                progress=100,
                persons_updated=updated_count,
                year=year,
                completed_at=datetime.now()
            )
        pipeline_task_id = message_data.get('pipeline_task_id')
        if pipeline_task_id:
            next_step = message_data.get('next_step')
            if next_step:
                # Trigger next step
                trigger_next_pipeline_step(message_data)
            else:
                # This was the last step, mark pipeline complete
                pipeline_year = message_data.get('pipeline_year')
                tasks_collection.update_one(
                    {"_id": ObjectId(pipeline_task_id)},
                    {"$set": {
                        "status": "completed",
                        "progress": 100,
                        "current_step": "completed",
                        f"steps.calculate_centrality.status": "completed",
                        "message": f"Pipeline completed successfully for year {pipeline_year}",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }}
                )
                logger.info(f"Pipeline {pipeline_task_id} completed for year {pipeline_year}")
        
        return {
            "status": "success",
            "persons_updated": updated_count,
            "year": year
        }
    except Exception as e:
        logger.error(f"Error calculating eigenvector centrality: {str(e)}", exc_info=True)
        if task_id:
            update_task_status(
                task_id,
                status="failed",
                message=f"Error: {str(e)}",
                error=str(e)
            )
        return {"status": "error", "message": str(e)}

def export_analysis(message_data):
    """
    Export analyzed persons data to JSON file by calling the /graph/persons/analyzed endpoint
    """
    year = message_data.get('year')
    pipeline_task_id = message_data.get('pipeline_task_id')
    
    if not year:
        logger.error("No year provided for export_analysis")
        return {"status": "error", "message": "No year provided"}
    
    try:
        logger.info(f"Exporting analysis data for year {year}...")
        
        # Update pipeline status
        if pipeline_task_id:
            tasks_collection.update_one(
                {"_id": ObjectId(pipeline_task_id)},
                {"$set": {
                    f"steps.export_analysis.status": "running",
                    "message": f"Exporting analysis data for year {year}",
                    "updated_at": datetime.now()
                }}
            )
        
        # Call the analyzed endpoint via HTTP
        import requests
        api_url = "http://localhost:8000/graph/persons/analyzed"
        params = {
            "year": year,
            "limit": 10000
        }
        logger.info(f"Calling API: {api_url} with params {params}")
        response = requests.get(api_url, params=params, timeout=300)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Retrieved {data.get('count', 0)} persons from API")
        if 'persons' in data and data['persons']:
            data['persons'] = sorted(
                data['persons'],
                key=lambda p: p.get('eigenvector_centrality', 0),
                reverse=True
            )
            logger.info(f"Sorted {len(data['persons'])} persons by centrality")
        
        analysis_dir = Path("flipke-iii-dun-broave/public/analysis")
        analysis_dir.mkdir(parents=True, exist_ok=True)
        output_file = analysis_dir / f"{year}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully exported analysis to {output_file}")
        
        # Mark pipeline complete
        if pipeline_task_id:
            tasks_collection.update_one(
                {"_id": ObjectId(pipeline_task_id)},
                {"$set": {
                    "status": "completed",
                    "progress": 100,
                    "current_step": "completed",
                    f"steps.export_analysis.status": "completed",
                    "message": f"Pipeline completed successfully for year {year}. Analysis exported to {output_file}",
                    "completed_at": datetime.now(),
                    "updated_at": datetime.now()
                }}
            )
            logger.info(f"Pipeline {pipeline_task_id} completed for year {year}")
        
        return {
            "status": "success",
            "year": year,
            "output_file": str(output_file),
            "persons_count": data.get('count', 0)
        }
        
    except Exception as e:
        logger.error(f"Error exporting analysis for year {year}: {str(e)}", exc_info=True)
        if pipeline_task_id:
            tasks_collection.update_one(
                {"_id": ObjectId(pipeline_task_id)},
                {"$set": {
                    "status": "failed",
                    f"steps.export_analysis.status": "failed",
                    "message": f"Export analysis failed: {str(e)}",
                    "error": str(e),
                    "updated_at": datetime.now()
                }}
            )
        return {"status": "error", "message": str(e)}

def run_full_pipeline(message_data):
    """
    Execute full pipeline: processes years sequentially by monitoring year pipeline completion
    and queuing the next year when ready
    """
    master_pipeline_id = message_data.get('master_pipeline_id')
    current_year = message_data.get('current_year')
    start_year = message_data.get('start_year')
    end_year = message_data.get('end_year')
    doForce = message_data.get('doForce', False)
    try:
        master_doc = tasks_collection.find_one({"_id": ObjectId(master_pipeline_id)})
        if not master_doc:
            logger.error(f"Master pipeline {master_pipeline_id} not found")
            return {"status": "error", "message": "Master pipeline not found"}
        total_years = end_year - start_year + 1
        from pathlib import Path
        import os
        worker_dir = Path(__file__).parent
        logger.info(f"Worker directory: {worker_dir}")
        logger.info(f"Current working directory: {os.getcwd()}")
        analysis_file = worker_dir / "data" / "analysis" / f"{current_year}.json"
        logger.info(f"Checking year {current_year}: file exists={analysis_file.exists()}, doForce={doForce}, absolute path={analysis_file.absolute()}")
        if analysis_file.exists() and not doForce:
            logger.info(f"Skipping year {current_year} - analysis file already exists")    
            completed_years = current_year - start_year + 1
            progress = int((completed_years / total_years) * 100)
            tasks_collection.update_one(
                {"_id": ObjectId(master_pipeline_id)},
                {"$set": {
                    "completed_years": completed_years,
                    "progress": progress,
                    "current_year": current_year,
                    f"year_pipelines.{current_year}": "skipped",
                    "message": f"Year {current_year} skipped (file exists). {completed_years}/{total_years} years processed",
                    "updated_at": datetime.now()
                }}
            )
            
            # Check if we're done
            if current_year >= end_year:
                tasks_collection.update_one(
                    {"_id": ObjectId(master_pipeline_id)},
                    {"$set": {
                        "status": "completed",
                        "progress": 100,
                        "message": f"All {total_years} years processed ({start_year}-{end_year})",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }}
                )
                logger.info(f"Full pipeline {master_pipeline_id} completed")
                return {"status": "success", "message": "Full pipeline completed"}
            
            # Queue next year immediately
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host='localhost',
                    port=5672,
                    credentials=pika.PlainCredentials('admin', 'admin')
                )
            )
            channel = connection.channel()
            channel.queue_declare(queue='tasks', durable=True)
            
            next_message = {
                "task": "run_full_pipeline",
                "master_pipeline_id": master_pipeline_id,
                "start_year": start_year,
                "end_year": end_year,
                "current_year": current_year + 1,
                "doForce": doForce,
                "timestamp": datetime.now().isoformat()
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='tasks',
                body=json.dumps(next_message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            connection.close()
            logger.info(f"Queued next year {current_year + 1}")
            return {"status": "success", "message": f"Year {current_year} skipped, queued next year"}
        year_pipeline_id = master_doc.get('year_pipelines', {}).get(str(current_year))        
        if year_pipeline_id == "skipped":
            logger.info(f"Year {current_year} was already skipped, moving to next")
            if current_year >= end_year:
                tasks_collection.update_one(
                    {"_id": ObjectId(master_pipeline_id)},
                    {"$set": {
                        "status": "completed",
                        "progress": 100,
                        "message": f"All {total_years} years processed ({start_year}-{end_year})",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }}
                )
                logger.info(f"Full pipeline {master_pipeline_id} completed")
                return {"status": "success", "message": "Full pipeline completed"}
            
            # Queue next year
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host='localhost',
                    port=5672,
                    credentials=pika.PlainCredentials('admin', 'admin')
                )
            )
            channel = connection.channel()
            channel.queue_declare(queue='tasks', durable=True)
            
            next_message = {
                "task": "run_full_pipeline",
                "master_pipeline_id": master_pipeline_id,
                "start_year": start_year,
                "end_year": end_year,
                "current_year": current_year + 1,
                "doForce": doForce,
                "timestamp": datetime.now().isoformat()
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='tasks',
                body=json.dumps(next_message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            connection.close()
            
            logger.info(f"Queued next year {current_year + 1}")
            return {"status": "success", "message": f"Already skipped, queued next year"}
        if year_pipeline_id and year_pipeline_id != "skipped":
            if analysis_file.exists() and not doForce:
                logger.info(f"Year {current_year} has existing pipeline but file already exists - marking as completed")
                tasks_collection.update_one(
                    {"_id": ObjectId(year_pipeline_id)},
                    {"$set": {
                        "status": "completed",
                        "message": "Analysis file already exists, pipeline stopped",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }}
                )
                
                # Update master to mark this year as done
                completed_years = current_year - start_year + 1
                progress = int((completed_years / total_years) * 100)
                
                tasks_collection.update_one(
                    {"_id": ObjectId(master_pipeline_id)},
                    {"$set": {
                        "completed_years": completed_years,
                        "progress": progress,
                        "message": f"Year {current_year} completed (file exists). {completed_years}/{total_years} years processed",
                        "updated_at": datetime.now()
                    }}
                )
                
                # Check if we're done
                if current_year >= end_year:
                    tasks_collection.update_one(
                        {"_id": ObjectId(master_pipeline_id)},
                        {"$set": {
                            "status": "completed",
                            "progress": 100,
                            "message": f"All {total_years} years processed ({start_year}-{end_year})",
                            "completed_at": datetime.now(),
                            "updated_at": datetime.now()
                        }}
                    )
                    logger.info(f"Full pipeline {master_pipeline_id} completed")
                    return {"status": "success", "message": "Full pipeline completed"}
                
                # Queue next year
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host='localhost',
                        port=5672,
                        credentials=pika.PlainCredentials('admin', 'admin')
                    )
                )
                channel = connection.channel()
                channel.queue_declare(queue='tasks', durable=True)
                
                next_message = {
                    "task": "run_full_pipeline",
                    "master_pipeline_id": master_pipeline_id,
                    "start_year": start_year,
                    "end_year": end_year,
                    "current_year": current_year + 1,
                    "doForce": doForce,
                    "timestamp": datetime.now().isoformat()
                }
                
                channel.basic_publish(
                    exchange='',
                    routing_key='tasks',
                    body=json.dumps(next_message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                connection.close()
                
                logger.info(f"Queued next year {current_year + 1}")
                return {"status": "success", "message": f"Year {current_year} file exists, queued next year"}
            
            year_doc = tasks_collection.find_one({"_id": ObjectId(year_pipeline_id)})
            if year_doc and year_doc.get('status') == 'completed':
                completed_years = current_year - start_year + 1
                progress = int((completed_years / total_years) * 100)
                logger.info(f"Year {current_year} completed ({completed_years}/{total_years})")
                tasks_collection.update_one(
                    {"_id": ObjectId(master_pipeline_id)},
                    {"$set": {
                        "completed_years": completed_years,
                        "progress": progress,
                        "message": f"Year {current_year} completed. {completed_years}/{total_years} years processed",
                        "updated_at": datetime.now()
                    }}
                )
                
                # Check if we're done
                if current_year >= end_year:
                    tasks_collection.update_one(
                        {"_id": ObjectId(master_pipeline_id)},
                        {"$set": {
                            "status": "completed",
                            "progress": 100,
                            "current_year": end_year,
                            "completed_years": total_years,
                            "message": f"All {total_years} years processed successfully ({start_year}-{end_year})",
                            "completed_at": datetime.now(),
                            "updated_at": datetime.now()
                        }}
                    )
                    logger.info(f"Full pipeline {master_pipeline_id} completed")
                    return {"status": "success", "message": "Full pipeline completed"}
                
                # Queue next year
                current_year += 1
                year_pipeline_id = None  # Reset for next year
            elif year_doc and year_doc.get('status') == 'failed':
                # Year pipeline failed
                tasks_collection.update_one(
                    {"_id": ObjectId(master_pipeline_id)},
                    {"$set": {
                        "status": "failed",
                        "message": f"Year {current_year} pipeline failed: {year_doc.get('message', 'Unknown error')}",
                        "updated_at": datetime.now()
                    }}
                )
                logger.error(f"Full pipeline {master_pipeline_id} failed at year {current_year}")
                return {"status": "error", "message": f"Year {current_year} pipeline failed"}
            else:
                # Year pipeline still running, re-queue monitoring task
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host='localhost',
                        port=5672,
                        credentials=pika.PlainCredentials('admin', 'admin')
                    )
                )
                channel = connection.channel()
                channel.queue_declare(queue='tasks', durable=True)
                import time
                time.sleep(10)
                monitor_message = {
                    "task": "run_full_pipeline",
                    "master_pipeline_id": master_pipeline_id,
                    "start_year": start_year,
                    "end_year": end_year,
                    "current_year": current_year,
                    "doForce": doForce,
                    "timestamp": datetime.now().isoformat()
                }
                
                channel.basic_publish(
                    exchange='',
                    routing_key='tasks',
                    body=json.dumps(monitor_message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                connection.close()
                
                logger.info(f"Year {current_year} pipeline still running, re-queued monitor")
                return {"status": "monitoring", "message": f"Monitoring year {current_year}"}
        
        # No year pipeline yet, create one for current year
        logger.info(f"Starting year pipeline for year {current_year}")
        
        # Update master pipeline status
        tasks_collection.update_one(
            {"_id": ObjectId(master_pipeline_id)},
            {"$set": {
                "status": "running",
                "current_year": current_year,
                "message": f"Processing year {current_year} ({current_year - start_year + 1}/{total_years})",
                "updated_at": datetime.now()
            }}
        )
        
        # Create year pipeline
        pipeline_doc = {
            "task_type": "year_analysis_pipeline",
            "year": current_year,
            "status": "running",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "current_step": "clear_graph",
            "steps": {
                "clear_graph": {"status": "pending", "task_id": None},
                "parse_entities": {"status": "pending", "task_id": None},
                "analyze_persons": {"status": "pending", "task_id": None},
                "calculate_centrality": {"status": "pending", "task_id": None},
                "export_analysis": {"status": "pending", "task_id": None}
            },
            "message": "Pipeline initialized, starting clear_graph step",
            "master_pipeline_id": master_pipeline_id
        }
        result = tasks_collection.insert_one(pipeline_doc)
        year_pipeline_id = str(result.inserted_id)
        
        # Store year pipeline ID in master
        tasks_collection.update_one(
            {"_id": ObjectId(master_pipeline_id)},
            {"$set": {
                f"year_pipelines.{current_year}": year_pipeline_id,
                "updated_at": datetime.now()
            }}
        )
        
        # Queue first step of year pipeline
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='tasks', durable=True)
        
        clear_message = {
            "task": "clear_graph",
            "pipeline_task_id": year_pipeline_id,
            "pipeline_year": current_year,
            "pipeline_step": "clear_graph",
            "next_step": "parse_entities",
            "timestamp": datetime.now().isoformat()
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='tasks',
            body=json.dumps(clear_message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        
        # Queue monitoring task to check completion
        monitor_message = {
            "task": "run_full_pipeline",
            "master_pipeline_id": master_pipeline_id,
            "start_year": start_year,
            "end_year": end_year,
            "current_year": current_year,
            "doForce": doForce,
            "timestamp": datetime.now().isoformat()
        }
        import time
        time.sleep(30)
        channel.basic_publish(
            exchange='',
            routing_key='tasks',
            body=json.dumps(monitor_message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        
        logger.info(f"Queued year {current_year} pipeline and monitoring task")
        return {"status": "success", "message": f"Year {current_year} pipeline started"}
        
    except Exception as e:
        logger.error(f"Error in run_full_pipeline: {str(e)}", exc_info=True)
        if master_pipeline_id:
            tasks_collection.update_one(
                {"_id": ObjectId(master_pipeline_id)},
                {"$set": {
                    "status": "failed",
                    "message": f"Full pipeline failed: {str(e)}",
                    "error": str(e),
                    "updated_at": datetime.now()
                }}
            )
        return {"status": "error", "message": str(e)}

def pre_modern_parse_entities(message_data):
    pipeline_task_id = message_data.get('pipeline_task_id')
    year = message_data.get('year')
    next_step = message_data.get('next_step')
    try:
        logger.info(f"Starting pipe parse_entities for year {year}, pipeline {pipeline_task_id}")
        json_file = Path("data/PER-annotations.json")
        tsv_file = Path("data/republic-paragraphs-2025-02-20.tsv")
        with open(json_file, 'r', encoding='utf-8') as f:
            annotations = json.load(f)
        year_prefix = f"{year}-"
        valid_resolution_ids = set()
        with open(tsv_file, 'r', encoding='utf-8') as f:
            next(f)
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    session_date = parts[0]
                    resolution_id = parts[1]
                    if session_date.startswith(year_prefix):
                        valid_resolution_ids.add(resolution_id)
        filtered_annotations = [
            ann for ann in annotations
            if ann.get('reference', {}).get('resolution_id') in valid_resolution_ids
        ]
        total_annotations = len(filtered_annotations)
        logger.info(f"Found {total_annotations} annotations for year {year}")
        if total_annotations == 0:
            logger.info(f"No annotations found for year {year}, triggering next step immediately")
            tasks_collection.update_one(
                {"_id": ObjectId(pipeline_task_id)},
                {"$set": {
                    f"steps.parse_entities.status": "completed",
                    "message": f"No annotations found for year {year}, skipping parse step",
                    "updated_at": datetime.now()
                }}
            )
            trigger_next_pipeline_step({
                'pipeline_task_id': pipeline_task_id,
                'pipeline_year': year,
                'pipeline_step': 'parse_entities',
                'next_step': next_step
            })
            return {"status": "success", "queued": 0, "message": "No annotations to parse"}
        
        batch_task_doc = {
            "task_type": "pre_modern_parse_batch",
            "status": "queuing",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "year": year,
            "total": total_annotations,
            "queued": 0,
            "processed": 0,
            "pipeline_task_id": pipeline_task_id,
            "pipeline_year": year,
            "next_step": next_step,
            "message": f"Queuing {total_annotations} annotations for year {year}"
        }
        result = tasks_collection.insert_one(batch_task_doc)
        batch_task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='tasks', durable=True)
        for i, annotation in enumerate(filtered_annotations):
            message = {
                "task": "pre_modern_parse_entity",
                "master_task_id": batch_task_id,
                "annotation": annotation,
                "annotation_index": i,
                "total_annotations": total_annotations,
                "timestamp": datetime.now().isoformat()
            }
            channel.basic_publish(
                exchange='',
                routing_key='tasks',
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
        connection.close()
        tasks_collection.update_one(
            {"_id": ObjectId(batch_task_id)},
            {"$set": {
                "status": "queued",
                "queued": total_annotations,
                "message": f"All {total_annotations} annotations queued for year {year}",
                "updated_at": datetime.now()
            }}
        )
        tasks_collection.update_one(
            {"_id": ObjectId(pipeline_task_id)},
            {"$set": {
                f"steps.parse_entities.task_id": batch_task_id,
                f"steps.parse_entities.status": "running",
                "message": f"Parsing {total_annotations} entities for year {year}",
                "updated_at": datetime.now()
            }}
        )
        logger.info(f"Pipe parse_entities queued {total_annotations} tasks")
        return {"status": "success", "queued": total_annotations}
    except Exception as e:
        logger.error(f"Error in pipeline_parse_entities: {str(e)}", exc_info=True)
        if pipeline_task_id:
            tasks_collection.update_one(
                {"_id": ObjectId(pipeline_task_id)},
                {"$set": {
                    "status": "failed",
                    "message": f"Parse entities step failed: {str(e)}",
                    "error": str(e),
                    "updated_at": datetime.now()
                }}
            )
        return {"status": "error", "message": str(e)}

def pipeline_analyze_persons(message_data):
    """
    Pipeline-specific analyze persons: queues all analysis tasks and triggers next step when done
    """
    pipeline_task_id = message_data.get('pipeline_task_id')
    year = message_data.get('year')
    next_step = message_data.get('next_step')
    
    try:
        logger.info(f"Starting pipe analyze_persons for year {year}, pipeline {pipeline_task_id}")
        with neo4j_driver.session() as session:
            result = session.run("MATCH (p:Person) RETURN p.id as person_id ORDER BY p.id")
            person_ids = [record["person_id"] for record in result]
        total_persons = len(person_ids)
        logger.info(f"Found {total_persons} persons to analyze")
        if total_persons == 0:
            logger.info(f"No persons found for year {year}, triggering next step immediately")
            tasks_collection.update_one(
                {"_id": ObjectId(pipeline_task_id)},
                {"$set": {
                    f"steps.analyze_persons.status": "completed",
                    "message": f"No persons found for year {year}, skipping analyze step",
                    "updated_at": datetime.now()
                }}
            )
            trigger_next_pipeline_step({
                'pipeline_task_id': pipeline_task_id,
                'pipeline_year': year,
                'pipeline_step': 'analyze_persons',
                'next_step': next_step
            })
            return {"status": "success", "queued": 0, "message": "No persons to analyze"}
        
        batch_task_doc = {
            "task_type": "analyze_persons_batch",
            "status": "queuing",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "total_persons": total_persons,
            "year": year,
            "queued_count": 0,
            "processed_count": 0,
            "pipeline_task_id": pipeline_task_id,
            "pipeline_year": year,
            "next_step": next_step,
            "message": f"Queuing {total_persons} person analysis tasks for year {year}"
        }
        result = tasks_collection.insert_one(batch_task_doc)
        batch_task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='tasks', durable=True)
        
        for i, person_id in enumerate(person_ids):
            message = {
                "task": "analyze_person_connections",
                "master_task_id": batch_task_id,
                "person_id": person_id,
                "person_index": i,
                "total_persons": total_persons,
                "year": year,
                "timestamp": datetime.now().isoformat()
            }
            channel.basic_publish(
                exchange='',
                routing_key='tasks',
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
        connection.close()
        tasks_collection.update_one(
            {"_id": ObjectId(batch_task_id)},
            {"$set": {
                "status": "queued",
                "queued_count": total_persons,
                "message": f"All {total_persons} person analysis tasks queued for year {year}",
                "updated_at": datetime.now()
            }}
        )
        tasks_collection.update_one(
            {"_id": ObjectId(pipeline_task_id)},
            {"$set": {
                f"steps.analyze_persons.task_id": batch_task_id,
                f"steps.analyze_persons.status": "running",
                "message": f"Analyzing {total_persons} persons for year {year}",
                "updated_at": datetime.now()
            }}
        )
        
        logger.info(f"Pipe analyze_persons queued {total_persons} tasks")
        return {"status": "success", "queued": total_persons}
        
    except Exception as e:
        logger.error(f"Error in pipeline_analyze_persons: {str(e)}", exc_info=True)
        if pipeline_task_id:
            tasks_collection.update_one(
                {"_id": ObjectId(pipeline_task_id)},
                {"$set": {
                    "status": "failed",
                    "message": f"Analyze persons step failed: {str(e)}",
                    "error": str(e),
                    "updated_at": datetime.now()
                }}
            )
        return {"status": "error", "message": str(e)}

def callback(ch, method, properties, body):
    logger.debug(f"Received message: {body.decode()}")
    try:
        message_data = json.loads(body)
        task_type = message_data.get('task')
        if task_type == "pre_modern_download":
            logger.info(f"Processing task: {task_type}")
            result = pre_modern_download(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "pre_modern_parse_entity":
            logger.debug(f"Processing task: {task_type}")
            result = pre_modern_parse_entity(message_data)
            logger.debug(f"Task completed: {result['status']}")
        elif task_type == "pre_modern_parse_document":
            logger.debug(f"Processing task: {task_type}")
            result = pre_modern_parse_document(message_data)
            logger.debug(f"Task completed: {result['status']}")
        elif task_type == "analyze_person_connections":
            logger.debug(f"Processing task: {task_type}")
            result = analyze_person_connections(message_data)
            logger.debug(f"Task completed: {result['status']}")
        elif task_type == "post_modern_scrape_page":
            logger.info(f"Processing task: {task_type}")
            result = post_modern_scrape_page(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "post_modern_download_document":
            logger.info(f"Processing task: {task_type}")
            result = post_modern_download_document(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "purge_queues":
            logger.info(f"Processing task: {task_type}")
            result = maintenance_purge_queues(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "delete_tasks":
            logger.info(f"Processing task: {task_type}")
            result = maintenance_delete_tasks(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "delete_documents":
            logger.info(f"Processing task: {task_type}")
            result = maintenance_delete_documents(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "clear_graph":
            logger.info(f"Processing task: {task_type}")
            result = maintenance_clear_graph(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "calculate_eigenvector_centrality":
            logger.info(f"Processing task: {task_type}")
            result = calculate_eigenvector_centrality(message_data)
            logger.info(f"Task completed: {result['status']}")
            trigger_next_pipeline_step(message_data)
        elif task_type == "pre_modern_parse_entities":
            logger.info(f"Processing task: {task_type}")
            result = pre_modern_parse_entities(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "pipeline_analyze_persons":
            logger.info(f"Processing task: {task_type}")
            result = pipeline_analyze_persons(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "export_analysis":
            logger.info(f"Processing task: {task_type}")
            result = export_analysis(message_data)
            logger.info(f"Task completed: {result['status']}")
        elif task_type == "run_full_pipeline":
            logger.info(f"Processing task: {task_type}")
            result = run_full_pipeline(message_data)
            logger.info(f"Task completed: {result['status']}")
        else:
            logger.warning(f"Unknown task type: {task_type}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except json.JSONDecodeError:
        logger.error("Invalid JSON message")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}", exc_info=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    logger.info("Worker started...")
    logger.info("Connecting to RabbitMQ...")
    max_retries = 5
    retry_delay = 5
    connection = None
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host='localhost',
                    port=5672,
                    credentials=pika.PlainCredentials('admin', 'admin'),
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )
            channel = connection.channel()
            channel.queue_declare(queue='tasks', durable=True)
            channel.queue_declare(queue='maintenance', durable=True)
            logger.info("Queue declared successfully: tasks")
            logger.info("Queue declared successfully: maintenance")
            channel.basic_qos(prefetch_count=20)
            channel.basic_consume(
                queue='tasks',
                on_message_callback=callback
            )
            channel.basic_consume(
                queue='maintenance',
                on_message_callback=callback
            )
            logger.info("Connected to RabbitMQ successfully")
            logger.info("Listening on 'tasks' and 'maintenance' queues (prefetch_count=20)")
            logger.info("Waiting for messages... (Press CTRL+C to stop)")
            channel.start_consuming()
            break
        except pika.exceptions.AMQPConnectionError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection failed: {str(e)}. Retrying in {retry_delay} seconds... ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                logger.error(f"Could not connect to RabbitMQ after {max_retries} attempts")
                logger.error("Make sure RabbitMQ is running: docker-compose up -d")
                logger.error(f"Last error: {str(e)}")
                sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
            if connection and not connection.is_closed:
                try:
                    connection.close()
                    logger.info("Connection closed cleanly")
                except:
                    pass
            sys.exit(0)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            if connection and not connection.is_closed:
                try:
                    connection.close()
                except:
                    pass
            sys.exit(1)

if __name__ == "__main__":
    main()
