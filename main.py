from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(
    title="Flipke d'n Dappere API",
    description="API for network analysis and visualization of named entities in historical governance documents from the Low Countries",
    version="1.0.0"
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
                padding: 40px;
                text-align: center;
            }
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            .header p {
                font-size: 1.2em;
                opacity: 0.9;
            }
            .content {
                padding: 40px;
            }
            .section {
                margin-bottom: 40px;
            }
            .section h2 {
                color: #667eea;
                margin-bottom: 20px;
                font-size: 1.8em;
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
                        <h3>Philip the Bold (1386)</h3>
                        <p>
                            In 1386, the Brabantian <a href="https://en.wikipedia.org/wiki/Philip_the_Bold" target="_blank">Philip the Bold</a> (Brabantian Dutch: Flipke d'n Dappere) established a Council Chamber in Lille for financial and legal matters concerning Flanders, Artois, Antwerp, and Mechlin. This regional body was a seed from which the <a href="https://en.wikipedia.org/wiki/States_General_of_the_Netherlands" target="_blank">States-General</a> of the Netherlands would later grow.
                        </p>
                    </div>
                </div>
                <div class="section">
                    <h2>🚀 Quick Links</h2>
                    <a href="/docs" class="btn">📖 API Documentation (Swagger)</a>
                    <a href="/entities/graph" class="btn">📋 Visualize Named Entities (Graph)</a>
                </div>

                <div class="section">
                    <h2>🔌 API Endpoints</h2>
                    <div class="endpoints">
                        <div class="endpoint">
                            <span class="method get">GET</span>
                            <h3>/entities</h3>
                            <p>Retrieve all named entities</p>
                        </div>
                        <div class="endpoint">
                            <span class="method get">GET</span>
                            <h3>/entities/{id}</h3>
                            <p>Retrieve a specific named entity by ID</p>
                        </div>
                        <div class="endpoint">
                            <span class="method post">POST</span>
                            <h3>/entities</h3>
                            <p>Add a new named entity</p>
                        </div>
                        <div class="endpoint">
                            <span class="method put">PUT</span>
                            <h3>/entities/{id}</h3>
                            <p>Update an existing named entity</p>
                        </div>
                        <div class="endpoint">
                            <span class="method delete">DELETE</span>
                            <h3>/entities/{id}</h3>
                            <p>Delete a named entity</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script>
            async function loadEntities() {
                try {
                    const response = await fetch('/entities');
                    const entities = await response.json();
                    const container = document.getElementById('entitiesContainer');
                    
                    if (entities.length === 0) {
                        container.innerHTML = '<p>No named entities found.</p>';
                        return;
                    }
                    
                    container.innerHTML = entities.map(entity => `
                        <div class="entity-item">
                            <div class="entity-year">${entity.year}</div>
                            <h3>${entity.title}</h3>
                            <p>${entity.description}</p>
                            <p><strong>Location:</strong> ${entity.location}</p>
                        </div>
                    `).join('');
                } catch (error) {
                    console.error('Error loading entities:', error);
                    document.getElementById('entitiesContainer').innerHTML = 
                        '<p>Error loading named entities.</p>';
                }
            }
            loadEntities();
        </script>
    </body>
    </html>
    """
    return html_content

@app.get("/entities", response_model=List[NamedEntity])
async def get_entities():
    """Retrieve all named entities"""
    # return entities_db

@app.get("/entities/{entity_id}", response_model=NamedEntity)
async def get_entity(entity_id: int):
    """Retrieve a specific named entity by ID"""
    # for entity in entities_db:
    #     if entity.id == entity_id:
    #         return entity
    raise HTTPException(status_code=404, detail="Named entity not found")

@app.post("/entities", response_model=NamedEntity, status_code=201)
async def create_entity(entity: NamedEntity):
    """Add a new named entity"""
    # Generate new ID
    # new_id = max([e.id for e in entities_db], default=0) + 1
    # entity.id = new_id
    # entities_db.append(entity)
    # return entity

@app.put("/entities/{entity_id}", response_model=NamedEntity)
async def update_entity(entity_id: int, updated_entity: NamedEntity):
    """Update an existing named entity"""
    # for i, entity in enumerate(entities_db):
    #     if entity.id == entity_id:
    #         updated_entity.id = entity_id
    #         entities_db[i] = updated_entity
    #         return updated_entity
    raise HTTPException(status_code=404, detail="Named entity not found")

@app.delete("/entities/{entity_id}")
async def delete_entity(entity_id: int):
    """Delete a named entity"""
    # for i, entity in enumerate(entities_db):
    #     if entity.id == entity_id:
    #         entities_db.pop(i)
    #         return {"message": "Named entity deleted"}
    raise HTTPException(status_code=404, detail="Named entity not found")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
