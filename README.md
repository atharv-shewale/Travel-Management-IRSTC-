# YatraAI - Smart Train Travel Assistant

A production-ready AI-powered train travel chatbot for India. It acts as a professional travel agent, capable of searching trains, checking schedules, fetching live seat availability, and checking PNR status via simulated external API integrations.

## Features
- **Frontend**: Clean, modern HTML/CSS/JS interface featuring dark mode, glassmorphism, and smooth animations.
- **Backend**: FastAPI built with Python, providing a fast and asynchronous API layer.
- **AI Engine**: Integrated with OpenAI's GPT models using function-calling for reliable data retrieval.
- **Database**: SQLite integration to persistently store chat history and manage sessions.
- **API Simulation**: Built-in mock wrappers mimicking real train data endpoints (IRCTC/RapidAPI equivalents).

## Folder Structure
```
train-chatbot/
│
├── backend/
│   ├── .env.example       # Example Environment variables
│   ├── main.py            # FastAPI entry point
│   ├── chatbot.py         # LLM logic & function tools definition
│   ├── train_api.py       # Mock API wrapper functions
│   ├── database.py        # SQLite Database connection and queries
│   └── requirements.txt   # Python dependencies
│
├── frontend/
│   ├── index.html         # Chat UI structure
│   ├── index.css          # Styling & Animations
│   └── app.js             # API communication & UI rendering
│
└── README.md
```

## Setup Instructions

### 1. Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   - Create a `.env` file in the `backend` directory.
   - Add your Groq API Key: `GROQ_API_KEY=your-api-key-here`

4. Run the FastAPI server:
   ```bash
   python main.py
   ```
   *The server will start on `http://localhost:8000`*

### 2. Frontend Setup
1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
   *The frontend will be available at the URL provided by Vite (usually http://localhost:5173).*

## Usage
1. Open `index.html` in your browser.
2. Ensure the backend server is running.
3. Start chatting! Try asking:
   - "Can you find a train from Delhi to Mumbai tomorrow?"
   - "What is the seat availability for train 12951 in 3A class?"
   - "Check my PNR status 1234567890."

## Future Enhancements
- Replace mock functions in `train_api.py` with actual API calls to RapidAPI or IRCTC.
- Implement rate limiting and authentication (JWT).
- Add robust caching (e.g., Redis) for frequent queries to reduce API costs.
