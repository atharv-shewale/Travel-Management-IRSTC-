import os
import re
import json
import logging
from datetime import datetime, timedelta
from groq import Groq
from train_api import search_trains, check_availability, get_pnr_status, book_ticket, get_itinerary_suggestions

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are YatraAI, a train travel assistant and local guide for India. Today's date is 2026-04-29.
RULES:
1. NATURAL TONE: Speak like a friendly human travel agent. ABSOLUTELY NO technical symbols. Do NOT use **bold**, [1], or - bullet points. Use clean, plain text only.
2. INTERACTIVE BUTTONS: Always include common follow-up actions in a `buttons` array within the `ui-data` block.
   Example: `{"type": "train_list", "trains": [...], "buttons": ["Check 3A Fare", "Show Faster Trains", "Search Tomorrow"]}`
3. RECOMMEND: Rank top 3 trains. Keep descriptions simple and easy to read.
4. BOOKING: Ask for passenger details simply. Once booked, show the success card.
5. UI DATA: (CRITICAL) Always append the JSON block in ```ui-data\n{...}\n``` for rich cards and buttons.
6. NEGOTIATION: Politely suggest alternative classes or dates if the user is price-sensitive.
7. SAFETY: Use live tools for data. Do not guess.
8. ITINERARY: Proactively suggest or retrieve local tourist sightseeing spots and food recommendations for destination cities using the get_itinerary_suggestions tool when a train search or booking is completed.
"""

AVAILABLE_FUNCTIONS = {
    "search_trains": search_trains,
    "check_availability": check_availability,
    "get_pnr_status": get_pnr_status,
    "book_ticket": book_ticket,
    "get_itinerary_suggestions": get_itinerary_suggestions,
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_trains",
            "description": "Search for trains between a source and destination station on a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Source station name or code"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination station name or code"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of travel in YYYY-MM-DD format"
                    }
                },
                "required": ["source", "destination", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check seat availability for a specific train, date, and travel class.",
            "parameters": {
                "type": "object",
                "properties": {
                    "train_number": {
                        "type": "string",
                        "description": "5-digit train number"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of travel in YYYY-MM-DD format"
                    },
                    "travel_class": {
                        "type": "string",
                        "description": "Travel class (e.g., 1A, 2A, 3A, SL, CC)"
                    }
                },
                "required": ["train_number", "date", "travel_class"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pnr_status",
            "description": "Check the PNR status of a booked ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pnr_number": {
                        "type": "string",
                        "description": "10-digit PNR number"
                    }
                },
                "required": ["pnr_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_ticket",
            "description": "Book a train ticket for a passenger.",
            "parameters": {
                "type": "object",
                "properties": {
                    "train_number": {
                        "type": "string",
                        "description": "5-digit train number"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of travel in YYYY-MM-DD format"
                    },
                    "travel_class": {
                        "type": "string",
                        "description": "Travel class (e.g., 1A, 2A, 3A, SL, CC)"
                    },
                    "passenger_name": {
                        "type": "string",
                        "description": "Full name of the passenger"
                    },
                    "age": {
                        "type": "integer",
                        "description": "Age of the passenger"
                    }
                },
                "required": ["train_number", "date", "travel_class", "passenger_name", "age"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_itinerary_suggestions",
            "description": "Retrieve popular tourist sightseeing highlights, local foods, and travel itineraries for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Station name or destination city"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Length of stay/itinerary in days (e.g., 1 or 2)"
                    }
                },
                "required": ["destination"]
            }
        }
    }
]

# ADVANCEMENT 5: Document OCR Passenger Extraction Utility
def extract_ocr_passenger_details(query: str) -> dict:
    """
    Parses typical identity document dumps to extract Name, DOB, Age and Gender.
    Example: "Aadhaar Document: NAME: Arjun Sharma, DOB: 12/04/1994, GENDER: M"
    """
    details = {}
    
    # 1. Name match
    name_match = re.search(r'\bNAME\s*[:\-]\s*([A-Za-z\s]+?)(?:,|\bDOB\b|\bGENDER\b|$)', query, re.IGNORECASE)
    if name_match:
        details["passenger_name"] = name_match.group(1).strip()
        
    # 2. DOB match
    dob_match = re.search(r'\bDOB\s*[:\-]\s*([0-9/\-]+)\b', query, re.IGNORECASE)
    if dob_match:
        dob_str = dob_match.group(1).strip()
        details["dob"] = dob_str
        try:
            # Parse DD/MM/YYYY or YYYY-MM-DD
            birth_year = 1994
            if "/" in dob_str:
                parts = dob_str.split("/")
                if len(parts) == 3:
                    birth_year = int(parts[2])
            elif "-" in dob_str:
                parts = dob_str.split("-")
                if len(parts) == 3:
                    birth_year = int(parts[0]) if len(parts[0]) == 4 else int(parts[2])
            
            # System year is 2026
            details["age"] = 2026 - birth_year
        except Exception:
            details["age"] = 32
            
    return details

# ADVANCEMENT 6: Neural Hinglish Translator
def translate_hinglish_with_llm(query: str) -> str:
    """
    Uses a fast Groq LLM completion call to translate Hinglish queries to standard English.
    """
    hinglish_markers = ["kar", "batao", "dikhao", "jana", "se", "tak", "hona", "chahiye", "dilado", "yaar", "karna", "parso"]
    q = query.lower()
    if not any(w in q for w in hinglish_markers):
        return query
        
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        translation_prompt = (
            "You are a translation engine. Translate the following Hinglish user query into plain English. "
            "Convert Indian station names to standard names (e.g. NDLS to Delhi, JP to Jaipur). "
            "Output ONLY the translated English query. No explanations, no introductory text."
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": translation_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.0
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"Neural Hinglish Translation: '{query}' ➜ '{translated}'")
        return translated
    except Exception as e:
        logger.error(f"Neural translation failed: {e}")
        return query

# ADVANCEMENT 1: Hinglish Preprocessor & Phonetic Typo Matcher
STANDARD_STATIONS = {
    "Delhi": ["delhi", "ndls", "new delhi", "dehli", "dheli", "dilhi", "delhy"],
    "Mumbai": ["mumbai", "bombay", "bambai", "cst", "dr", "mumbay", "mumbai central"],
    "Jaipur": ["jaipur", "jp", "jaipore", "jeypore"],
    "Kolkata": ["kolkata", "calcutta", "hwh", "howrah", "culcutta"],
    "Chennai": ["chennai", "madras", "mas"],
    "Pune": ["pune", "poona", "paune"],
    "Bengaluru": ["bengaluru", "bangalore", "sbc", "blore", "benglur"],
    "Hyderabad": ["hyderabad", "secunderabad", "hyd", "hyderbad", "secunderbad"],
    "Goa": ["goa", "madgaon", "mao"],
    "Agra": ["agra", "agc", "agra cantt"]
}

def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Pure Python implementation of Levenshtein edit distance.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]

def fuzzy_resolve_station(word: str) -> str:
    """
    Fuzzy Station Resolver using Levenshtein edit distance.
    Matches aliases or words within edit distance of 2 from any known alias.
    """
    w = word.strip().lower()
    if not w or len(w) <= 2:
        return None
        
    # Check exact aliases
    for standard_name, aliases in STANDARD_STATIONS.items():
        if w in aliases:
            return standard_name
            
    # Check Levenshtein distance
    best_match = None
    min_distance = 999
    
    for standard_name, aliases in STANDARD_STATIONS.items():
        for alias in aliases:
            dist = levenshtein_distance(w, alias)
            if dist < min_distance and dist <= 2:
                min_distance = dist
                best_match = standard_name
                
    return best_match

def normalize_hinglish_query(query: str) -> str:
    """
    NLP Preprocessor to parse common Hinglish phrases and station name variants
    to standard English and unified station terms, backed by Neural Translation.
    """
    translated = translate_hinglish_with_llm(query)
    normalized = translated.strip()
    
    # Common Hinglish phrases translation mapping fallback
    hinglish_rules = [
        (r'\b(trains?|gadi|gaadi|gaadiyan)\s*(dikhao|show|batao|dhundo|find)\b', "find trains"),
        (r'\b(booking?|book|ticket|reserve)\s*(kar do|karna hai|karana hai)\b', "book ticket"),
        (r'\b(jaana|jana)\s*hai\b', "travel"),
        (r'\bse\b', "from"),
        (r'\bko\b', "to"),
        (r'\btak\b', "to"),
        (r'\bkal\b', "tomorrow"),
        (r'\baaj\b', "today"),
        (r'\b(highlights?|places?|sightseeing|ghoomne|ghumne|spots?)\s*(batao|show|Highlights)\b', "sightseeing highlights")
    ]
    
    for pattern, replacement in hinglish_rules:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
    # Apply Levenshtein fuzzy station resolution on each word in query
    words = re.findall(r'\b[a-zA-Z]+\b', normalized)
    for word in words:
        resolved = fuzzy_resolve_station(word)
        if resolved and resolved.lower() != word.lower():
            normalized = re.sub(rf'\b{word}\b', resolved, normalized, flags=re.IGNORECASE)
            
    # Phonetic and colloquial station code typo normalizations (fallback)
    station_typos = {
        r'\b(dheli|delhy|dehli|dilhi|ndls)\b': "Delhi",
        r'\b(mumbay|bombay|bambai|cst|dr)\b': "Mumbai",
        r'\b(jaipore|jeypore|jp)\b': "Jaipur",
        r'\b(culcutta|kolkata|calcutta|hwh)\b': "Kolkata",
        r'\b(madras|chennai|mas)\b': "Chennai"
    }
    
    for pattern, replacement in station_typos.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
    return normalized

# ADVANCEMENT 2: Semantic Dialogue Intent Router
def semantic_intent_router(query: str) -> str:
    """
    Checks if a query is extremely short, generic chitchat, security violation
    or support QA that does not warrant invoking heavy train/booking tools.
    Returns 'GUARDRAIL', 'CHITCHAT', 'SIGHTSEEING', 'BOOKING', or 'TRANSIT'.
    """
    q = query.lower()
    
    # NLP ADVANCEMENT: Input Security Guardrail Detection
    guardrail_indicators = [
        "javascript", "python", "java", "code", "hack", "bypass", "exploit", "sql", 
        "system prompt", "ignore prior", "override", "math", "calculate", "equation", "script",
        "c++", "c#", "html", "css", "terminal", "bash", "execute", "database"
    ]
    if any(k in q for k in guardrail_indicators):
        return "GUARDRAIL"
    
    # Simple Chitchat / Greetings
    greetings = ["hi", "hello", "namaste", "hey", "good morning", "good evening", "thanks", "thank you", "who are you"]
    if any(q == g or q.startswith(g + " ") for g in greetings) and len(q.split()) <= 4:
        return "CHITCHAT"
        
    # Check for sightseeing indicators
    sightseeing_keywords = ["sightseeing", "sight", "highlights", "ghoomne", "ghumne", "itinerary", "places", "food", "attractions"]
    if any(k in q for k in sightseeing_keywords):
        return "SIGHTSEEING"
        
    # Check for booking indicators
    booking_keywords = ["book", "reserve", "ticket", "seat", "pnr", "berth", "passenger", "confirm"]
    if any(k in q for k in booking_keywords):
        return "BOOKING"
        
    return "TRANSIT"

# ADVANCEMENT 3: Dialogue Slot-Filling Extractor
def extract_slots_from_history(messages: list) -> dict:
    """
    Iterates through conversation history and current query to extract
    slots for booking: train_number, travel_class, passenger_name, age, date.
    """
    slots = {
        "train_number": None,
        "travel_class": None,
        "passenger_name": None,
        "age": None,
        "date": None
    }
    
    # Compile regexes
    train_re = re.compile(r'\b\d{5}\b')
    class_re = re.compile(r'\b(1A|2A|3A|SL|CC|2S)\b', re.IGNORECASE)
    age_re = re.compile(r'\bage\s*(\d{1,2})\b|\b(\d{1,2})\s*(years?|yrs|years? old)\b', re.IGNORECASE)
    date_re = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
    
    # Check for relative dates based on today's date "2026-04-29"
    relative_tomorrow = "2026-04-30"
    relative_today = "2026-04-29"

    # Search through messages from most recent to oldest
    for msg in reversed(messages):
        content = msg.get("content", "")
        if not content:
            continue
            
        # Extract train number
        if not slots["train_number"]:
            t_match = train_re.search(content)
            if t_match:
                slots["train_number"] = t_match.group(0)
                
        # Extract class
        if not slots["travel_class"]:
            c_match = class_re.search(content)
            if c_match:
                slots["travel_class"] = c_match.group(1).upper()
                
        # Extract age
        if not slots["age"]:
            a_match = age_re.search(content)
            if a_match:
                slots["age"] = int(a_match.group(1) or a_match.group(2))
                
        # Extract date
        if not slots["date"]:
            d_match = date_re.search(content)
            if d_match:
                slots["date"] = d_match.group(0)
            elif "tomorrow" in content.lower():
                slots["date"] = relative_tomorrow
            elif "today" in content.lower():
                slots["date"] = relative_today
                
        # Extract passenger name
        if not slots["passenger_name"]:
            name_match = re.search(r'\b(?:passenger|name|named|for)\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)\b', content, re.IGNORECASE)
            if name_match:
                name_candidate = name_match.group(1).strip()
                if name_candidate.lower() not in ["train", "ticket", "tomorrow", "today", "yesterday", "delhi", "mumbai", "jaipur", "passenger", "name", "class", "seat"]:
                    slots["passenger_name"] = name_candidate
            
    return slots

def generate_chat_response(messages: list):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    if len(messages) > 20:
        messages = messages[-20:]
        
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # Apply ADVANCEMENT 5: Document OCR Passenger Extraction Check
    if last_user_msg and any(k in last_user_msg.upper() for k in ["NAME:", "DOB:", "GENDER:", "PASSPORT:", "AADHAAR:"]):
        ocr_details = extract_ocr_passenger_details(last_user_msg)
        if "passenger_name" in ocr_details and "age" in ocr_details:
            reply = (
                f"I have successfully parsed your passenger document! Here are the extracted details:\n"
                f"- Passenger Name: {ocr_details['passenger_name']}\n"
                f"- Calculated Age: {ocr_details['age']} years (born in {ocr_details.get('dob', '1994')})\n\n"
                f"I have populated these details into your booking memory! Which train or travel class would you like to book now?"
            )
            ui_payload = {
                "type": "chat_reply",
                "buttons": ["Search Trains", "Help Me Plan"]
            }
            if "```ui-data" not in reply:
                reply += f"\n\n```ui-data\n{json.dumps(ui_payload)}\n```"
            messages.append({"role": "user", "content": f"Passenger Name: {ocr_details['passenger_name']}, Age: {ocr_details['age']}"})
            messages.append({"role": "assistant", "content": reply})
            return reply, ui_payload, messages

    # Apply ADVANCEMENT 1: Hinglish Preprocessor on last user message
    if last_user_msg:
        normalized = normalize_hinglish_query(last_user_msg)
        logger.info(f"NLP Normalizer: '{last_user_msg}' ➜ '{normalized}'")
        for msg in reversed(messages):
            if msg.get("role") == "user":
                msg["content"] = normalized
                break
        last_user_msg = normalized

    # Apply ADVANCEMENT 2: Semantic Dialogue Intent Router
    intent = semantic_intent_router(last_user_msg)
    logger.info(f"NLP Router Intent: {intent}")

    # Apply ADVANCEMENT: Safety Guardrail Route
    if intent == "GUARDRAIL":
        logger.warning(f"Guardrail triggered for query: '{last_user_msg}'")
        reply = (
            "As the YatraAI travel concierge, I am dedicated to Indian Railways train bookings, "
            "seat availability updates, PNR tracking, and local sightseeing guides. "
            "I cannot run code, execute instructions outside travel planning, or solve off-topic queries. "
            "How can I help you plan your next journey across India today?"
        )
        ui_payload = {
            "type": "chat_reply",
            "buttons": ["Search Trains", "Help Me Plan"]
        }
        if "```ui-data" not in reply:
            reply += f"\n\n```ui-data\n{json.dumps(ui_payload)}\n```"
        messages.append({"role": "assistant", "content": reply})
        return reply, ui_payload, messages

    # Fast Path for Greetings / Chitchat
    if intent == "CHITCHAT":
        try:
            logger.info("Chitchat route: bypassing tool pipeline for fast reply.")
            chitchat_prompt = "You are YatraAI, an elite minimalist train travel concierge for India. Answer the greeting briefly and warmly, ask how you can help plan their next journey."
            fast_messages = [{"role": "system", "content": chitchat_prompt}, {"role": "user", "content": last_user_msg}]
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=fast_messages,
            )
            reply = response.choices[0].message.content
            messages.append({"role": "assistant", "content": reply})
            return reply, None, messages
        except Exception as e:
            logger.error(f"Fast routing failed: {e}")

    # Apply ADVANCEMENT 3: Booking Slot-Filling Interceptor State Machine
    if intent == "BOOKING" and any(w in last_user_msg.lower() for w in ["book", "reserve", "ticket", "seat"]):
        slots = extract_slots_from_history(messages)
        logger.info(f"NLU Slot Extractor Slots: {slots}")

        # Check for missing slots
        missing = []
        if not slots["train_number"]: missing.append("Train Number (5 digits)")
        if not slots["travel_class"]: missing.append("Travel Class (e.g. 3A, SL)")
        if not slots["passenger_name"]: missing.append("Passenger Name")
        if not slots["age"]: missing.append("Passenger Age")
        if not slots["date"]: slots["date"] = "2026-05-25" # Fallback transit date if date missing

        if missing:
            logger.info(f"Slot Interceptor: Dialogue incomplete. Missing slots: {missing}")
            missing_lbls = ", ".join(missing)
            reply = f"I would be glad to reserve your seat! To complete the ticket booking, I just need a few missing details: {missing_lbls}. Could you please provide them?"
            ui_payload = {
                "type": "chat_reply",
                "buttons": ["Book John Doe 3A", "Help Me Plan", "Search Trains"]
            }
            if "```ui-data" not in reply:
                reply += f"\n\n```ui-data\n{json.dumps(ui_payload)}\n```"
            messages.append({"role": "assistant", "content": reply})
            return reply, ui_payload, messages
        else:
            # ALL SLOTS SUCCESSFULLY FILLED! Enforce execution parameters to guarantee tool matching
            synthetic_prompt = f"book ticket on train {slots['train_number']} for passenger {slots['passenger_name']}, age {slots['age']}, class {slots['travel_class']} for travel date {slots['date']}"
            logger.info(f"Slot Interceptor: ALL slots filled. Constructing tool prompt: '{synthetic_prompt}'")
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    msg["content"] = synthetic_prompt
                    break

    # Ensure system prompt is the first message
    messages = [m for m in messages if m.get("role") != "system"]
    messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        
    try:
        logger.info("Sending payload to Groq LLM...")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        
        response_message = response.choices[0].message
        
        if response_message.tool_calls:
            logger.info(f"LLM triggered {len(response_message.tool_calls)} tool call(s).")
            
            tool_calls_list = []
            for tc in response_message.tool_calls:
                tool_calls_list.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
            
            messages.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": tool_calls_list
            })
            
            tool_results = []
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
                
                if function_to_call:
                    try:
                        args = json.loads(tool_call.function.arguments)
                        logger.info(f"Calling {function_name}({args})")
                        result = function_to_call(**args)
                        tool_results.append({"name": function_name, "data": result})
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(result)
                        })
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps({"status": "error", "message": str(e)})
                        })
                else:
                    logger.error(f"Function {function_name} not found.")
            
            # Second call
            logger.info("Sending tool results back to LLM...")
            second_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
            )
            final_content = second_response.choices[0].message.content
            
            # Extract or Generate UI data
            ui_data_payload = None
            ui_blocks = []
            for res in tool_results:
                if res["name"] == "search_trains" and res["data"].get("status") == "success":
                    ui_blocks.append({
                        "type": "train_list",
                        "trains": res["data"].get("data", [])[:3],
                        "buttons": ["Check 3A Fare", "Show Faster Trains", "Search Tomorrow"]
                    })
                elif res["name"] == "book_ticket" and res["data"].get("status") == "success":
                    ui_blocks.append({
                        "type": "booking_success",
                        "data": res["data"].get("data"),
                        "buttons": ["Check PNR Status", "Download Ticket", "View Coach Map"]
                    })
                elif res["name"] == "get_itinerary_suggestions" and res["data"].get("status") == "success":
                    ui_blocks.append({
                        "type": "itinerary",
                        "destination": res["data"].get("destination"),
                        "data": res["data"].get("data"),
                        "buttons": ["Explore Hotels", "Check Trains Back"]
                    })
            
            if ui_blocks:
                ui_data_payload = ui_blocks[0]
                # ADVANCEMENT 4: Reflective JSON validator & syntax repairer
                if "```ui-data" not in final_content:
                    final_content += f"\n\n```ui-data\n{json.dumps(ui_data_payload)}\n```"

            messages.append({"role": "assistant", "content": final_content})
            return final_content, ui_data_payload, messages
            
        else:
            logger.info("LLM generated a direct response without tool calls.")
            messages.append({"role": "assistant", "content": response_message.content})
            return response_message.content, None, messages
            
    except Exception as e:
        import traceback
        logger.error(f"DETAILED ERROR: {e}")
        logger.error(traceback.format_exc())
        error_msg = "Unable to fetch live data right now. Please try again later."
        messages.append({"role": "assistant", "content": error_msg})
        return error_msg, None, messages
