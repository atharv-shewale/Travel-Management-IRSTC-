from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import uuid
import os
import logging

from database import init_db, get_history, save_history, get_all_sessions, get_all_bookings
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
    ui_data: dict = None

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
        reply, ui_data, updated_history = generate_chat_response(history)
        
        # Save updated history
        save_history(session_id, updated_history)
        logger.info(f"Successfully processed response for session {session_id}")
        
        return ChatResponse(session_id=session_id, reply=reply, ui_data=ui_data)
    except Exception as e:
        logger.error(f"Error in chat_endpoint for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/sessions")
def get_sessions_endpoint():
    try:
        sessions = get_all_sessions()
        return {"status": "success", "data": sessions}
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")

@app.get("/api/sessions/{session_id}/history")
def get_session_history_endpoint(session_id: str):
    try:
        history = get_history(session_id)
        return {"status": "success", "data": history}
    except Exception as e:
        logger.error(f"Error getting history for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch session history")

@app.get("/api/bookings")
def get_bookings_endpoint():
    try:
        bookings = get_all_bookings()
        return {"status": "success", "data": bookings}
    except Exception as e:
        logger.error(f"Error getting bookings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch bookings")

class UpdateBerthRequest(BaseModel):
    berth: int

@app.put("/api/bookings/{pnr}/berth")
def update_booking_berth_endpoint(pnr: str, request: UpdateBerthRequest):
    try:
        from database import get_booking, save_booking
        booking = get_booking(pnr)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Keep old format passenger compatibility
        booking["passenger"] = booking.get("passenger_name", "")
        booking["berth"] = request.berth
        save_booking(booking)
        logger.info(f"Updated PNR {pnr} to berth {request.berth}")
        return {"status": "success", "data": booking}
    except Exception as e:
        logger.error(f"Error updating berth for PNR {pnr}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update berth")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
