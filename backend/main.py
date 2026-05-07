from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import uuid
import os
import logging

from database import init_db, get_history, save_history
from chatbot import generate_chat_response

# Configure Logging for Observability
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Train Travel Chatbot API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    logger.info("Starting up FastAPI application and initializing DB...")
    init_db()

class ChatRequest(BaseModel):
    session_id: str = None
    message: str

class ChatResponse(BaseModel):
    session_id: str
    reply: str

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    session_id = request.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"Created new session: {session_id}")
        
    logger.info(f"Received message for session {session_id}: '{request.message}'")
    
    try:
        history = get_history(session_id)
        history.append({"role": "user", "content": request.message})
        
        # Get response from chatbot
        reply, updated_history = generate_chat_response(history)
        
        # Save updated history
        save_history(session_id, updated_history)
        logger.info(f"Successfully processed response for session {session_id}")
        
        return ChatResponse(session_id=session_id, reply=reply)
    except Exception as e:
        logger.error(f"Error in chat_endpoint for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
