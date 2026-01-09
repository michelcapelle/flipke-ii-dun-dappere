import os
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import pika
import json
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
from neo4j import GraphDatabase
from pathlib import Path
import time
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Flipke d'n Dappere API",
    description="API for network analysis and visualization of named entities in historical governance documents from the Low Countries",
    version="1.0.0"
)
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

class NamedEntity(BaseModel):
    id: Optional[int] = None
    name: str

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Flipke d'n Dappere API</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                text-align: center;
            }
            .header h1 {
                font-size: 1.75em;
                margin-bottom: 10px;
            }
            .header p {
                font-size: 1.0em;
                opacity: 0.9;
            }
            .content {
                padding: 40px;
                padding-bottom: 0px;
            }
            .section {
                margin-bottom: 40px;
            }
            .section h2 {
                color: #667eea;
                margin-bottom: 20px;
                font-size: 1.25em;
            }
            .card {
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 5px;
            }
            .card h3 {
                color: #333;
                margin-bottom: 10px;
                font-size: 1.0em;
            }
            .card p {
                color: #666;
                line-height: 1.6;
            }
            .btn {
                display: inline-block;
                padding: 12px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin-right: 10px;
                margin-bottom: 10px;
                transition: transform 0.2s;
                width: 15%;
                text-align: center;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            .endpoints {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            .endpoint {
                background: white;
                border: 2px solid #e0e0e0;
                padding: 20px;
                border-radius: 8px;
                transition: all 0.3s;
            }
            .endpoint:hover {
                border-color: #667eea;
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.2);
            }
            .method {
                display: inline-block;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 0.9em;
                margin-bottom: 10px;
            }
            .get { background: #61affe; color: white; }
            .post { background: #49cc90; color: white; }
            .put { background: #fca130; color: white; }
            .delete { background: #f93e3e; color: white; }
            .entity-item {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                border-left: 4px solid #764ba2;
            }
            .entity-year {
                color: #667eea;
                font-weight: bold;
                font-size: 1.2em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌐 Flipke d'n Dappere API</h1>
                <p>Flipke is an API for network analysis and visualization of named entities in historical governance documents from the Low Countries</p>
            </div>
            <div class="content">
                <div class="section">
                    <h2>📚 About This Project</h2>
                    <div class="card">
                        <h3>Philip the Bold (1342–1404)</h3>
                        <p>
                            In 1386, the Brabantian <a href="https://en.wikipedia.org/wiki/Philip_the_Bold" target="_blank">Philip the Bold</a> (Brabantian Dutch: Flipke d'n Dappere) established a Council Chamber in Lille for financial and legal matters concerning Flanders, Artois, Antwerp, and Mechlin. This regional body was a seed from which the <a href="https://en.wikipedia.org/wiki/States_General_of_the_Netherlands" target="_blank">States-General</a> of the Netherlands would later grow.
                        </p>
                    </div>
                </div>
                <div class="section">
                    <h2>🚀 Quick Links</h2>
                    <a href="/docs" target="_blank" class="btn">📖 API</a>
                    <a href="http://localhost:15672/#/queues/%2F/tasks" target="_blank" class="btn">⏳ Queues</a>
                    <a href="http://localhost:8081/db/flipke_db/" target="_blank" class="btn">📂 Docs</a>
                    <a href="http://localhost:7474/" target="_blank" class="btn">🔗 Graph</a>
                    <a href="http://localhost:4200/" target="_blank" class="btn">📅 Timeline</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.get("/graph/persons", tags=["graph"])
async def get_persons(limit: int = Query(100, description="Maximum number of persons to return")):
    """
    Retrieve all Person nodes from Neo4j graph database
    
    - **limit**: Maximum number of persons to return (default: 100)
    """
    try:
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (p:Person)
                RETURN p.id as id
                ORDER BY p.id ASC
                LIMIT $limit
            """, limit=limit)
            persons = []
            for record in result:
                persons.append({
                    "id": record["id"]
                })
            return {
                "status": "success",
                "count": len(persons),
                "limit": limit,
                "persons": persons
            }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving persons from Neo4j: {str(e)}"
        )

@app.post("/graph/persons/analyze", tags=["graph", "persons"])
async def analyze_persons_connections(year: Optional[int] = Query(None, description="Year to associate with this analysis (e.g., 1600)")):
    """
    Queue tasks to analyze connections for all Person nodes in the graph.
    
    For each person, the worker will:
    - Count connections to other persons through shared documents
    - Retrieve all names associated with the person
    - Store results in MongoDB with the specified year
    
    Use the returned status_endpoint to monitor progress.
    
    - **year**: Optional year to tag this analysis with (e.g., 1600)
    """
    try:
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (p:Person)
                RETURN p.id as id
                ORDER BY p.id ASC
            """)
            person_ids = [record["id"] for record in result]
        if not person_ids:
            raise HTTPException(
                status_code=404,
                detail="No persons found in graph. Please parse entities first using /eras/pre-modern/parse/entities."
            )
        total_persons = len(person_ids)
        task_doc = {
            "task_type": "analyze_persons_batch",
            "status": "queuing",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "total_persons": total_persons,
            "queued_count": 0,
            "processed_count": 0,
            "analysis_year": year,
            "message": f"Queuing person analysis tasks{f' for year {year}' if year else ''}"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        
        queued_count = 0
        for i, person_id in enumerate(person_ids):
            message = {
                "task": "analyze_person_connections",
                "master_task_id": task_id,
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
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            queued_count += 1
            
            if (i + 1) % 1000 == 0:
                tasks_collection.update_one(
                    {"_id": ObjectId(task_id)},
                    {"$set": {
                        "queued_count": queued_count,
                        "message": f"Queued {queued_count}/{total_persons} person analysis tasks",
                        "updated_at": datetime.now()
                    }}
                )
        
        connection.close()
        
        tasks_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {
                "status": "queued",
                "queued_count": queued_count,
                "message": f"All {queued_count} person analysis tasks queued for processing",
                "updated_at": datetime.now()
            }}
        )
        
        response = {
            "status": "queued",
            "message": f"{queued_count} person analysis tasks have been queued successfully",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "total_persons": total_persons,
            "analysis_year": year,
            "worker_connected": worker_connected
        }
        
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
            response["note"] = "Tasks will remain in queue until a worker connects"
        else:
            response["note"] = f"Worker(s) will process {queued_count} person analysis tasks. This may take several minutes."
        return response 
    except HTTPException:
        raise
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing analysis tasks: {str(e)}"
        )

@app.get("/graph/persons/analyzed", tags=["graph", "persons"])
async def get_analyzed_persons(
    person_id: Optional[str] = Query(None, description="Filter by specific person ID (e.g., P0003409)"),
    year: Optional[int] = Query(None, description="Filter by analysis year (e.g., 1600)"),
    limit: int = Query(100, ge=1, le=100000, description="Maximum number of persons to return (1-100000)"),
    skip: int = Query(0, ge=0, description="Number of persons to skip (for pagination)")
):
    """
    Retrieve analyzed persons from MongoDB with connection counts and names.
    
    Returns persons that have been analyzed using /graph/persons/analyze endpoint.
    Each person includes:
    - person_id
    - connection_count (number of connections to other persons)
    - names (list of all associated names)
    - year (if filtered)
    - analyzed_at (timestamp of analysis)
    
    - **person_id**: Optional. Filter to return a specific person by ID
    - **year**: Optional. Filter to only return persons analyzed for a specific year
    - **limit**: Maximum number of persons to return (default: 100, max: 100000)
    - **skip**: Number of persons to skip for pagination (default: 0)
    """
    try:
        query_filter = {}
        if person_id is not None:
            query_filter["person_id"] = person_id
        if year is not None:
            query_filter["year"] = year
        persons_cursor = person_analysis_collection.find(
            query_filter,
            {"_id": 0}
        ).sort("eigenvector_centrality", -1).skip(skip).limit(limit)
        persons = list(persons_cursor)
        for person in persons:
            pid = person["person_id"]
            names_filter = {"person_id": pid}
            if year is not None:
                names_filter["year"] = year    
            names_cursor = person_names_collection.find(
                names_filter,
                {"_id": 0, "name": 1}
            )
            person["names"] = [n["name"] for n in names_cursor]
            with neo4j_driver.session() as session:
                documents_result = session.run("""
                    MATCH (p:Person {id: $person_id})-[:MENTIONED_IN]->(d:Document)
                    RETURN DISTINCT d.id AS document_id
                    ORDER BY d.id
                """, person_id=pid)
                
                person["documents"] = [record["document_id"] for record in documents_result]
            
            if "analyzed_at" in person:
                person["analyzed_at"] = person["analyzed_at"].isoformat()
        total_count = person_analysis_collection.count_documents(query_filter)
        response = {
            "status": "success",
            "count": len(persons),
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "persons": persons
        }
        if person_id is not None:
            response["person_id"] = person_id
        if year is not None:
            response["year"] = year
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving analyzed persons from MongoDB: {str(e)}"
        )

@app.post("/graph/persons/centrality", tags=["graph", "persons"])
async def calculate_eigenvector_centrality(year: int = Query(..., description="Year to calculate centrality for (e.g., 1600)")):
    """
    Calculate normalized eigenvector centrality for persons analyzed in a specific year.
    
    This will:
    - Filter persons from person_analysis collection by the specified year
    - Use Neo4j Graph Data Science library to calculate eigenvector centrality
    - Consider indirect connections between persons through shared documents (Person -> Document <- Person)
    - Update person_analysis records in MongoDB with the centrality scores for that year
    
    Use the returned status_endpoint to monitor progress.
    
    - **year**: Required. Year to calculate centrality for (e.g., 1600)
    """
    try:
        person_count = person_analysis_collection.count_documents({"year": year})
        if person_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No persons found in person_analysis collection for year {year}. Please run /graph/persons/analyze?year={year} first."
            )
        task_doc = {
            "task_type": "calculate_centrality",
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "total_persons": person_count,
            "year": year,
            "message": f"Task queued for year {year}, waiting for worker"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        
        message = {
            "task_id": task_id,
            "task": "calculate_eigenvector_centrality",
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
        
        response = {
            "status": "queued",
            "message": f"Eigenvector centrality calculation task has been queued successfully for year {year}",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "year": year,
            "total_persons": person_count,
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
        return response
    except HTTPException:
        raise
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing centrality calculation: {str(e)}"
        )

@app.get("/graph/stats", tags=["graph"])
async def get_graph_stats():
    """
    Get statistics about the Neo4j graph database.
    
    Returns:
    - Count of nodes per label/type (Person, Document, Name, etc.)
    - Count of relationships per type (MENTIONED_IN, HAS_NAME, RELATES_TO, etc.)
    - Total node and relationship counts
    """
    try:
        with neo4j_driver.session() as session:
            node_labels_result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(n) as count
                ORDER BY count DESC
            """)
            nodes_by_label = {record["label"]: record["count"] for record in node_labels_result if record["label"]}
            rel_types_result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            """)
            relationships_by_type = {record["type"]: record["count"] for record in rel_types_result if record["type"]}
            total_nodes = sum(nodes_by_label.values())
            total_relationships = sum(relationships_by_type.values())
        return {
            "status": "success",
            "nodes": {
                "by_label": nodes_by_label,
                "total": total_nodes
            },
            "relationships": {
                "by_type": relationships_by_type,
                "total": total_relationships
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving graph statistics: {str(e)}"
        )

@app.get("/health", tags=["maintenance"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/queues/status", tags=["queues", "maintenance"])
async def get_all_queues_status():
    """
    Get the status of the unified tasks queue
    """
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        
        try:
            method = channel.queue_declare(queue='tasks', passive=True)
            queue_info = {
                "queue_name": "tasks",
                "messages_ready": method.method.message_count,
                "consumers": method.method.consumer_count,
                "status": "active"
            }
        except pika.exceptions.ChannelClosedByBroker:
            queue_info = {
                "queue_name": "tasks",
                "messages_ready": 0,
                "consumers": 0,
                "status": "not_created"
            }
        
        connection.close()
        return {
            "status": "success",
            "queue": queue_info,
            "note": f"{queue_info['messages_ready']} message(s) waiting in queue, {queue_info['consumers']} worker(s) connected"
        }
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while checking queue status: {str(e)}"
        )

@app.get("/tasks/latest", tags=["tasks"])
async def get_latest_task_status(limit: int = Query(1, ge=1, le=100, description="Number of latest tasks to retrieve (1-100)")):
    """
    Get the most recently created tasks
    
    - **limit**: Number of tasks to retrieve (default: 10, max: 100)
    """
    try:
        tasks = list(tasks_collection.find(
            {},
            sort=[("created_at", -1)],
            limit=limit
        ))        
        if not tasks:
            raise HTTPException(status_code=404, detail="No tasks found")
        for task in tasks:
            task['_id'] = str(task['_id'])
            if 'created_at' in task:
                task['created_at'] = task['created_at'].isoformat()
            if 'updated_at' in task:
                task['updated_at'] = task['updated_at'].isoformat()
            if 'completed_at' in task:
                task['completed_at'] = task['completed_at'].isoformat()
        return {
            "count": len(tasks),
            "limit": limit,
            "tasks": tasks
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching task status: {str(e)}"
        )

@app.delete("/queues", tags=["queues", "maintenance"])
async def purge_all_queues():
    """
    Queue a task to purge (empty) all queues in RabbitMQ.
    
    Use the returned `status_endpoint` to monitor progress.
    """
    try:
        task_doc = {
            "task_type": "purge_queues",
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "message": "Task queued, waiting for worker"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='maintenance', durable=True, passive=False)
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        message = {
            "task_id": task_id,
            "task": "purge_queues",
            "timestamp": datetime.now().isoformat()
        }
        channel.basic_publish(
            exchange='',
            routing_key='maintenance',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        response = {
            "status": "queued",
            "message": "Queue purge task has been queued successfully",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing the task: {str(e)}"
        )

@app.delete("/tasks", tags=["tasks", "maintenance"])
async def delete_all_tasks():
    """
    Queue a task to delete all task documents from MongoDB.
    
    This will permanently remove all task tracking records from the database.
    Use the returned `status_endpoint` to monitor progress.
    """
    try:
        task_doc = {
            "task_type": "delete_tasks",
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "message": "Task queued, waiting for worker"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='maintenance', durable=True, passive=False)
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        message = {
            "task_id": task_id,
            "task": "delete_tasks",
            "timestamp": datetime.now().isoformat()
        }
        channel.basic_publish(
            exchange='',
            routing_key='maintenance',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        response = {
            "status": "queued",
            "message": "Delete tasks task has been queued successfully",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing the task: {str(e)}"
        )

@app.delete("/graph", tags=["graph"])
async def clear_graph():
    """
    Queue a task to delete all nodes and relationships from Neo4j.
    
    This will permanently remove:
    - All Person nodes
    - All Document nodes
    - All Name nodes
    - All relationships (MENTIONED_IN, HAS_NAME, RELATES_TO, etc.)
    
    ⚠️ Warning: This action cannot be undone!
    Use the returned `status_endpoint` to monitor progress.
    """
    try:
        task_doc = {
            "task_type": "clear_graph",
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "message": "Task queued, waiting for worker"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='maintenance', durable=True, passive=False)
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        message = {
            "task_id": task_id,
            "task": "clear_graph",
            "timestamp": datetime.now().isoformat()
        }
        channel.basic_publish(
            exchange='',
            routing_key='maintenance',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        response = {
            "status": "queued",
            "message": "Clear graph task has been queued successfully",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing the task: {str(e)}"
        )

@app.delete("/documents", tags=["documents", "maintenance"])
async def delete_all_documents():
    """
    Queue a task to delete all documents from MongoDB.
    
    This will permanently remove all document records from the documents collection.
    Use the returned `status_endpoint` to monitor progress.
    """
    try:
        task_doc = {
            "task_type": "delete_documents",
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "message": "Task queued, waiting for worker"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='maintenance', durable=True, passive=False)
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        message = {
            "task_id": task_id,
            "task": "delete_documents",
            "timestamp": datetime.now().isoformat()
        }
        channel.basic_publish(
            exchange='',
            routing_key='maintenance',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        response = {
            "status": "queued",
            "message": "Delete documents task has been queued successfully",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing the task: {str(e)}"
        )

@app.delete("/all", tags=["maintenance"])
async def delete_all():
    """
    Queue tasks to execute all DELETE operations: clear queues, tasks, documents, and graph.
    
    This will queue separate tasks for:
    1. Purge all messages from RabbitMQ queues
    2. Delete all task documents from MongoDB
    3. Delete all document records from MongoDB
    4. Delete all nodes and relationships from Neo4j
    
    ⚠️ Warning: This action cannot be undone! All data will be permanently removed.
    """
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='maintenance', durable=True, passive=False)
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        queued_tasks = []
        
        for task_type in ['purge_queues', 'delete_documents', 'delete_tasks', 'clear_graph']:
            task_doc = {
                "task_type": task_type,
                "status": "queued",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "progress": 0,
                "message": "Task queued, waiting for worker"
            }
            result = tasks_collection.insert_one(task_doc)
            task_id = str(result.inserted_id)
            message = {
                "task_id": task_id,
                "task": task_type,
                "timestamp": datetime.now().isoformat()
            }
            channel.basic_publish(
                exchange='',
                routing_key='maintenance',
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            queued_tasks.append({
                "task_type": task_type,
                "task_id": task_id,
                "status_endpoint": f"/tasks/{task_id}"
            })
        connection.close()
        response = {
            "status": "queued",
            "message": f"Queued {len(queued_tasks)} delete tasks successfully",
            "tasks": queued_tasks,
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing tasks: {str(e)}"
        )

@app.get("/tasks/{task_id}", tags=["tasks"])
async def get_task_status(task_id: str):
    """
    Get the status of a specific task
    
    - **task_id**: The unique identifier of the task
    """
    try:
        if not ObjectId.is_valid(task_id):
            raise HTTPException(status_code=400, detail="Invalid task ID format")
        task = tasks_collection.find_one({"_id": ObjectId(task_id)})
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        task['_id'] = str(task['_id'])
        if 'created_at' in task:
            task['created_at'] = task['created_at'].isoformat()
        if 'updated_at' in task:
            task['updated_at'] = task['updated_at'].isoformat()
        if 'completed_at' in task:
            task['completed_at'] = task['completed_at'].isoformat()
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching task status: {str(e)}"
        )

@app.get("/tasks/latest/pipeline/year", tags=["tasks", "pipelines"])
async def get_latest_year_pipeline():
    """
    Get the latest year pipeline task.
    
    Returns the most recent task with task_type = "year_analysis_pipeline",
    sorted by creation date.
    """
    try:
        task = tasks_collection.find_one(
            {"task_type": "year_analysis_pipeline"},
            sort=[("created_at", -1)]
        )
        if not task:
            raise HTTPException(
                status_code=404,
                detail="No year analysis pipeline task found"
            )
        task['_id'] = str(task['_id'])
        if 'created_at' in task:
            task['created_at'] = task['created_at'].isoformat()
        if 'updated_at' in task:
            task['updated_at'] = task['updated_at'].isoformat()
        if 'completed_at' in task:
            task['completed_at'] = task['completed_at'].isoformat()
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching latest pipeline: {str(e)}"
        )

@app.post("/eras/pre-modern/parse/entities", tags=["eras"])
async def parse_pre_modern_graph_entities(year: Optional[int] = Query(None, description="Filter annotations by year (e.g., 1600). Only process annotations with resolution_ids from this year.")):
    """
    Queue tasks to parse data/PER-annotations.json and create graph in Neo4j.
    
    Each annotation will be queued as a separate task for parallel processing.
    The worker will create for each annotation:
    - Person nodes from entity field
    - Document nodes from reference.resolution_id
    - NamedEntity nodes from reference.tag_text
    - Relationships: Person MENTIONED_IN Document
    - Relationships: Person IS_NAMED NamedEntity
    
    Use the returned status_endpoint to monitor progress.
    
    - **year**: Optional. Filter to only process annotations from documents in this year (e.g., 1600)
    """
    json_file = Path("data/PER-annotations.json")
    if not json_file.exists():
        raise HTTPException(
            status_code=404,
            detail="PER-annotations.json not found. Please download the data first using /eras/pre-modern/download/entities."
        )
    tsv_file = Path("data/republic-paragraphs-2025-02-20.tsv")
    if year is not None and not tsv_file.exists():
        raise HTTPException(
            status_code=404,
            detail="republic-paragraphs-2025-02-20.tsv not found. Year filtering requires this file. Please download it first using /eras/pre-modern/download/documents."
        ) 
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            annotations = json.load(f)
        filtered_annotations = annotations
        valid_resolution_ids = None
        if year is not None:
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
            if not valid_resolution_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"No documents found for year {year} in TSV file."
                )
            filtered_annotations = [
                ann for ann in annotations
                if ann.get('reference', {}).get('resolution_id') in valid_resolution_ids
            ]
            if not filtered_annotations:
                raise HTTPException(
                    status_code=404,
                    detail=f"No annotations found with resolution_ids from year {year}."
                )
        total_annotations = len(filtered_annotations)
        task_doc = {
            "task_type": "pre_modern_parse_batch",
            "file_path": str(json_file),
            "status": "queuing",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "total_annotations": total_annotations,
            "queued_count": 0,
            "filter_year": year,
            "documents_in_year": len(valid_resolution_ids) if valid_resolution_ids else None,
            "message": f"Queuing individual annotation tasks{f' for year {year}' if year else ''}"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        queued_count = 0
        for i, annotation in enumerate(filtered_annotations):
            message = {
                "task": "pre_modern_parse",
                "master_task_id": task_id,
                "annotation": annotation,
                "annotation_index": i,
                "total_annotations": total_annotations,
                "timestamp": datetime.now().isoformat()
            }
            channel.basic_publish(
                exchange='',
                routing_key='tasks',
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            queued_count += 1
            if (i + 1) % 1000 == 0:
                tasks_collection.update_one(
                    {"_id": ObjectId(task_id)},
                    {"$set": {
                        "queued_count": queued_count,
                        "message": f"Queued {queued_count}/{total_annotations} annotations{f' for year {year}' if year else ''}",
                        "updated_at": datetime.now()
                    }}
                )
        connection.close()
        tasks_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {
                "status": "queued",
                "queued_count": queued_count,
                "message": f"All {queued_count} annotations queued for processing{f' (filtered to year {year})' if year else ''}",
                "updated_at": datetime.now()
            }}
        )
        response = {
            "status": "queued",
            "message": f"{queued_count} annotation tasks have been queued successfully{f' for year {year}' if year else ''}",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "total_annotations": total_annotations,
            "worker_connected": worker_connected
        }        
        if year is not None:
            response["filter_year"] = year
            response["documents_in_year"] = len(valid_resolution_ids)
            response["original_annotations"] = len(annotations)
            response["annotations_queued"] = total_annotations
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
            response["note"] = "Tasks will remain in queue until a worker connects"
        else:
            response["note"] = f"Worker(s) will process {queued_count} annotation tasks. This may take several minutes."
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing the task: {str(e)}"
        )

@app.get("/eras/pre-modern/download/entities", tags=["eras"])
async def download_pre_modern_entities(doForce: bool = Query(False, description="Force download even if file already exists")):
    """
    Queue a download task for the pre-modern era entities.
    
    ⚠️ **Important:** The file is 2.0 GB in size. Download may take significant time.
    
    Use the returned `status_endpoint` or `/tasks/latest` to monitor progress.
    The task will show status: queued → downloading → completed
    
    - **doForce**: If True, download even if the file already exists
    """
    try:
        task_doc = {
            "task_type": "pre_modern_download",
            "url": "https://zenodo.org/records/15495712/files/PER-annotations.json",
            "filename": "PER-annotations.json",
            "doForce": doForce,
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "message": "Task queued, waiting for worker"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0        
        message = {
            "task_id": task_id,
            "task": "pre_modern_download",
            "url": "https://zenodo.org/records/15495712/files/PER-annotations.json",
            "filename": "PER-annotations.json",
            "doForce": doForce,
            "timestamp": datetime.now().isoformat()
        }
        channel.basic_publish(
            exchange='',
            routing_key='tasks',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        connection.close()
        response = {
            "status": "queued",
            "message": "Download task has been queued successfully",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
            response["note"] = "Task will remain in queue until a worker connects"
        else:
            response["note"] = "Worker will process this task shortly"
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing the task: {str(e)}"
        )

@app.get("/eras/pre-modern/download/documents", tags=["eras"])
async def download_pre_modern_documents(doForce: bool = Query(False, description="Force download even if file already exists")):
    """
    Queue a download task for the pre-modern era documents.
    
    Use the returned `status_endpoint` or `/tasks/latest` to monitor progress.
    The task will show status: queued → downloading → extracting → completed
    
    - **doForce**: If True, download even if the file already exists
    """
    try:
        task_doc = {
            "task_type": "pre_modern_download",
            "url": "https://zenodo.org/records/15074656/files/republic-paragraphs-2025-02-20.tsv.gz",
            "filename": "republic-paragraphs-2025-02-20.tsv.gz",
            "doForce": doForce,
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "message": "Task queued, waiting for worker"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        queue_info = channel.queue_declare(queue='tasks', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0        
        message = {
            "task_id": task_id,
            "task": "pre_modern_download",
            "url": "https://zenodo.org/records/15074656/files/republic-paragraphs-2025-02-20.tsv.gz",
            "filename": "republic-paragraphs-2025-02-20.tsv.gz",
            "doForce": doForce,
            "timestamp": datetime.now().isoformat()
        }
        channel.basic_publish(
            exchange='',
            routing_key='tasks',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        connection.close()
        response = {
            "status": "queued",
            "message": "Download task has been queued successfully",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
            response["note"] = "Task will remain in queue until a worker connects"
        else:
            response["note"] = "Worker will process this task shortly"
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing the task: {str(e)}"
        )

@app.get("/eras/post-modern/download", tags=["eras"])
async def download_post_modern_data(doForce: bool = Query(False, description="Force download even if already processed")):
    """
    Queue a download task for the post-modern era data from repository.overheid.nl.
    
    This will:
    1. Scrape the main listing page at https://repository.overheid.nl/frbr/sgd?start=1
    2. Extract all document links from browse__list
    3. Follow pagination links to queue additional pages
    4. Each page URL will be queued and processed by worker
    5. Worker will download actual document files to data/post-modern/
    
    Use the returned `status_endpoint` to monitor progress.
    
    - **doForce**: If True, process even if already done
    """
    try:
        task_doc = {
            "task_type": "post_modern_download",
            "url": "https://repository.overheid.nl/frbr/sgd?start=1",
            "doForce": doForce,
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "message": "Task queued, waiting for worker"
        }
        result = tasks_collection.insert_one(task_doc)
        task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        queue_info = channel.queue_declare(queue='post_modern_download', durable=True, passive=False)
        worker_connected = queue_info.method.consumer_count > 0
        message = {
            "task_id": task_id,
            "task": "post_modern_scrape_page",
            "url": "https://repository.overheid.nl/frbr/sgd?start=1",
            "doForce": doForce,
            "timestamp": datetime.now().isoformat()
        }
        channel.basic_publish(
            exchange='',
            routing_key='post_modern_download',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        connection.close()
        response = {
            "status": "queued",
            "message": "Post-modern download task has been queued successfully",
            "task_id": task_id,
            "status_endpoint": f"/tasks/{task_id}",
            "worker_connected": worker_connected
        }
        if not worker_connected:
            response["warning"] = "No worker is currently connected! Start the worker with: python worker.py"
            response["note"] = "Task will remain in queue until a worker connects"
        else:
            response["note"] = "Worker will scrape pages and queue document downloads"
        return response
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to RabbitMQ. Make sure RabbitMQ is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while queuing the task: {str(e)}"
        )

@app.post("/eras/pre-modern/pipeline/full", tags=["eras", "pipelines"])
async def run_pre_modern_full_pipeline(
    doForce: bool = Query(False, description="Force pipeline to run for all years even if analysis files exist")
):
    """
    Execute complete analysis pipeline for all pre-modern years (1576-1796).
    
    This pipeline processes each year sequentially, one at a time, in ascending order.
    For each year, it runs the complete year analysis pipeline:
    1. Clear graph
    2. Parse entities for that year
    3. Analyze person connections
    4. Calculate eigenvector centrality
    5. Export analysis
    
    ⚠️ This is a long-running operation that will process 221 years sequentially.
    Each year is completed before the next begins.
    
    Use the returned status_endpoint to monitor progress.
    
    Note: This endpoint queues the master pipeline task. A worker process will handle
    the sequential execution of year pipelines via the queue system.
    
    - **doForce**: If False (default), skip years where data/analysis/{year}.json already exists
    """
    try:
        worker_dir = Path(__file__).parent
        start_year = 1576
        end_year = 1796
        if not doForce:
            for year in range(start_year, end_year + 1):
                analysis_file = worker_dir / "flipke-iii-dun-broave" / "public" / "analysis" / f"{year}.json"
                if not analysis_file.exists():
                    start_year = year
                    break
        total_years = end_year - start_year + 1
        master_pipeline_doc = {
            "task_type": "pre_modern_full_pipeline",
            "status": "queued",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "current_year": start_year,
            "start_year": start_year,
            "end_year": end_year,
            "total_years": total_years,
            "completed_years": 0,
            "year_pipelines": {},
            "do_force": doForce,
            "message": f"Pipeline initialized. Will process years {start_year}-{end_year} sequentially{' (forced)' if doForce else ''}"
        }
        result = tasks_collection.insert_one(master_pipeline_doc)
        master_pipeline_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='tasks', durable=True, passive=False)
        message = {
            "task": "run_full_pipeline",
            "master_pipeline_id": master_pipeline_id,
            "start_year": start_year,
            "end_year": end_year,
            "current_year": start_year,
            "do_force": doForce,
            "timestamp": datetime.now().isoformat()
        }
        channel.basic_publish(
            exchange='',
            routing_key='tasks',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        return {
            "status": "queued",
            "message": f"Pre-modern full pipeline started. Processing years {start_year}-{end_year} sequentially{' (forced)' if doForce else ''}",
            "master_pipeline_id": master_pipeline_id,
            "start_year": start_year,
            "end_year": end_year,
            "total_years": total_years,
            "do_force": doForce,
            "status_endpoint": f"/tasks/{master_pipeline_id}",
            "note": "Each year will be processed completely before the next begins" + (" (will skip years with existing analysis files)" if not doForce else " (will force all years)")
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error starting full pipeline: {str(e)}"
        )

@app.get("/tasks/latest/pipeline/full", tags=["tasks", "pipelines"])
def get_latest_full_pipeline_status():
    """
    Get detailed status of the latest full pipeline including the current year pipeline.
    
    Returns:
    - Master pipeline information (overall progress, current year, etc.)
    - Current year pipeline details if available
    
    Retrieves the most recently created full pipeline.
    """
    try:
        master_doc = tasks_collection.find_one(
            {"task_type": "pre_modern_full_pipeline"},
            sort=[("created_at", -1)]
        )
        if not master_doc:
            raise HTTPException(status_code=404, detail="No full pipeline found")
        master_pipeline_id = str(master_doc["_id"])
        master_doc["_id"] = master_pipeline_id
        for field in ["created_at", "updated_at", "completed_at"]:
            if field in master_doc and master_doc[field]:
                master_doc[field] = master_doc[field].isoformat()
        current_year = master_doc.get("current_year")
        current_year_pipeline = None
        if current_year:
            year_pipelines = master_doc.get("year_pipelines", {})
            year_pipeline_id = year_pipelines.get(str(current_year))
            if year_pipeline_id:
                year_doc = tasks_collection.find_one({"_id": ObjectId(year_pipeline_id)})
                if year_doc:
                    year_doc["_id"] = str(year_doc["_id"])
                    for field in ["created_at", "updated_at", "completed_at"]:
                        if field in year_doc and year_doc[field]:
                            year_doc[field] = year_doc[field].isoformat()
                    current_year_pipeline = year_doc
        
        return {
            "status": "success",
            "master_pipeline": master_doc,
            "current_year_pipeline": current_year_pipeline
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving latest full pipeline status: {str(e)}"
        )

@app.post("/eras/pre-modern/pipeline/year", tags=["eras", "pipelines"])
def run_pre_modern_year_pipeline(
    year: int = Query(..., description="Year to analyze (e.g., 1600)"),
    doForce: bool = Query(False, description="Force pipeline to run even if analysis file exists")
):
    """
    Execute a complete analysis pipeline for a specific year.
    
    Pipeline steps:
    1. Clear graph - Remove all existing data from Neo4j
    2. Parse entities - Parse and import entities for the specified year
    3. Analyze persons - Analyze connections between persons
    4. Calculate centrality - Calculate eigenvector centrality
    5. Export analysis - Export results to data/analysis/{year}.json
    
    Each step is monitored and the next step only starts when the previous completes successfully.
    Use the returned status_endpoint to monitor the pipeline progress.
    
    - **year**: Year to analyze (e.g., 1600)
    - **doForce**: If False (default), skip pipeline if data/analysis/{year}.json already exists
    """
    try:
        pipeline_doc = {
            "task_type": "year_analysis_pipeline",
            "year": year,
            "status": "running",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "progress": 0,
            "current_step": "clear_graph",
            "do_force": doForce,
            "steps": {
                "clear_graph": {"status": "pending", "task_id": None},
                "parse_entities": {"status": "pending", "task_id": None},
                "analyze_persons": {"status": "pending", "task_id": None},
                "calculate_centrality": {"status": "pending", "task_id": None},
                "export_analysis": {"status": "pending", "task_id": None}
            },
            "message": "Pipeline initialized, starting clear_graph step"
        }
        result = tasks_collection.insert_one(pipeline_doc)
        pipeline_task_id = str(result.inserted_id)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='localhost',
                port=5672,
                credentials=pika.PlainCredentials('admin', 'admin')
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='tasks', durable=True, passive=False)
        message = {
            "task": "clear_graph",
            "pipeline_task_id": pipeline_task_id,
            "pipeline_year": year,
            "pipeline_step": "clear_graph",
            "next_step": "parse_entities",
            "timestamp": datetime.now().isoformat()
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='tasks',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        
        return {
            "status": "queued",
            "message": f"Year analysis pipeline started for year {year}",
            "pipeline_task_id": pipeline_task_id,
            "year": year,
            "status_endpoint": f"/tasks/{pipeline_task_id}",
            "steps": ["clear_graph", "parse_entities", "analyze_persons", "calculate_centrality", "export_analysis"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error starting pipeline: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
