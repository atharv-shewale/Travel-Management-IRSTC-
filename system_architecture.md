# YatraAI: System Architecture & Data Flow

## 🔄 End-to-End Data Flow

The system is designed as a modular, state-aware pipeline where data flows seamlessly from the user down to external APIs and back.

1. **USER INPUT**
   - The user inputs a natural language query in the frontend UI.
   - *Example: "I want to go from Pune to Delhi tomorrow"*

2. **FRONTEND LAYER**
   - The React/Vanilla JS UI captures the input.
   - It sends an HTTP POST request to the backend `/api/chat` endpoint, attaching the unique `session_id` and user `message`.
   - The UI immediately displays the user's message and a typing indicator.

3. **BACKEND CONTROLLER (FastAPI)**
   - Receives the payload and extracts `session_id` and `message`.
   - Fetches the persistent conversation history for this `session_id` from the SQLite database.
   - Appends the new user message to the context and forwards it to the AI Layer.

4. **AI LAYER (LLM / OpenAI)**
   - The LLM processes the complete conversation history against its System Prompt.
   - **Intent Extraction**: It extracts entities like `source`, `destination`, `date`, `class`, and `passengers`.
   - **Decision Making**:
     - *Path A*: If required data is missing (e.g., date), it triggers the **Clarification Engine** to generate a follow-up question.
     - *Path B*: If all data is present, it issues a **Tool Call** (e.g., `search_trains`).

5. **FUNCTION CALLING LAYER**
   - The backend intercepts the LLM's tool call.
   - It routes the request to the corresponding Python wrapper function:
     - `search_trains(source, destination, date)`
     - `check_availability(train_number, date, travel_class)`
     - `get_pnr_status(pnr_number)`

6. **EXTERNAL API LAYER & BACKEND PROCESSING**
   - The wrapper function calls the external service (simulated IRCTC/RapidAPI).
   - It implements **caching** for frequent searches to optimize performance.
   - The raw API response is normalized into a standard JSON format (e.g., `Train Object`).
   - Errors (e.g., timeouts, 500s) are caught and handled.

7. **AI RESPONSE GENERATION**
   - The structured JSON response is appended to the message context as a `tool` role message.
   - The context is sent back to the LLM.
   - The LLM acts as a **Recommendation Engine**, analyzing the JSON data, ranking results by duration/availability, and generating a natural, human-readable response.

8. **FRONTEND RESPONSE**
   - The backend saves the updated conversation history to the SQLite database.
   - The final AI response is sent back to the frontend.
   - The frontend renders the formatted response and hides the typing indicator.

---

## 🔗 Feature Connection Logic

### 1. Train Search
- **Trigger**: User provides source + destination (+ optional date).
- **Action**: LLM maps intent to `search_trains()`.
- **Flow**: Fetches normalized train lists. The Recommendation Engine ranks the top 3-5 results based on duration and availability before presenting them.

### 2. Availability Check
- **Trigger**: User selects a specific train from the search list, or explicitly asks "is seat available on train 12951".
- **Action**: LLM triggers `check_availability()`.
- **Flow**: Evaluates specific class availability and returns real-time seating status.

### 3. PNR Status
- **Trigger**: User provides a 10-digit PNR number.
- **Action**: LLM triggers `get_pnr_status()`.
- **Flow**: Returns booking status, current status, and passenger berth details.

### 4. Clarification Engine
- **Trigger**: Incomplete intent mapping (e.g., "Find trains to Mumbai").
- **Action**: The LLM halts tool execution and asks: "Where will you be departing from, and on what date?" The context is preserved in the SQLite session memory so the user only needs to provide the missing piece.

### 5. Fallback System
- **Trigger**: API returns empty lists or errors.
- **Action**: LLM suggests alternatives like nearby stations or different dates, or outputs a graceful degradation message: *"Unable to fetch live data right now."*

---

## 🧠 State Management

State is inherently managed via the **Conversation History Window**.
- **Storage**: SQLite table (`session_id` -> `history JSON`).
- **Mechanism**: Every interaction appends to this history. The LLM acts as the state manager, remembering `source`, `destination`, and `selected train` across multi-turn interactions. This prevents the bot from asking repeated questions and maintains context seamlessly.

---

## ⚙️ Data Structure Design

### Train Object
```json
{
  "train_number": "12951",
  "train_name": "Rajdhani Express",
  "departure_time": "16:30",
  "arrival_time": "08:30",
  "duration": "16h 00m",
  "classes": ["1A", "2A", "3A"],
  "fare_estimate": 2800,
  "availability": "AVAILABLE 10"
}
```

### PNR Object
```json
{
  "pnr_number": "1234567890",
  "status": "CNF",
  "passengers": [
    { "berth": "B1-23", "status": "CNF" }
  ]
}
```

---

## 📊 Observability & Optimization
- **Logging**: Python's `logging` module captures all incoming user queries, tool invocations, execution times, and errors.
- **Caching**: Python's `functools.lru_cache` (or a dict-based TTL cache) is used on the API wrapper level to prevent redundant external API hits for identical searches within a short timeframe.
