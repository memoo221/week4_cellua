from fastapi import FastAPI
from api.routes import health, dataset, query, voice
from services.dataset_store import initialize_database
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
initialize_database()
app = FastAPI()
app.include_router(health.router)
app.include_router(dataset.router)
app.include_router(query.router)
app.include_router(voice.router)
