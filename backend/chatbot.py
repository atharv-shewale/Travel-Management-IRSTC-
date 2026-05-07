import os
import json
import logging
from groq import Groq
from train_api import search_trains, check_availability, get_pnr_status

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are YatraAI, a train travel assistant for India. Today's date is 2026-04-29.
RULES:
1. CLARIFY: If missing Source, Destination, or Date for a search, ask for them. Do not guess.
2. RECOMMEND: Rank top 3 trains by duration/availability.
3. FORMAT: Show Name(Number), Departure->Arrival, Duration, Fare, Availability. Label fare as "Estimated Fare".
4. SAFETY: Do NOT hallucinate data. ALWAYS use the provided JSON tools to fetch data. Do NOT use XML or <function> tags.
"""

AVAILABLE_FUNCTIONS = {
    "search_trains": search_trains,
    "check_availability": check_availability,
    "get_pnr_status": get_pnr_status,
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
    }
]

def generate_chat_response(messages: list):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # Token Saving: Truncate history to keep only the last 8 messages
    if len(messages) > 8:
        messages = messages[-8:]
        
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
            # We need to append the assistant's tool call message
            msg_dict = {
                "role": "assistant",
                "content": response_message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    } for tool_call in response_message.tool_calls
                ]
            }
            messages.append(msg_dict)
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
                
                if function_to_call:
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                        logger.info(f"Executing function: {function_name} with args: {function_args}")
                        function_response = function_to_call(**function_args)
                    except Exception as e:
                        logger.error(f"Error executing function {function_name}: {e}")
                        function_response = {"status": "error", "message": str(e)}
                        
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(function_response),
                    })
            
            # Second call with tool results
            logger.info("Sending tool results back to LLM for final response...")
            second_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
            )
            final_content = second_response.choices[0].message.content
            messages.append({"role": "assistant", "content": final_content})
            return final_content, messages
            
        else:
            logger.info("LLM generated a direct response without tool calls.")
            messages.append({"role": "assistant", "content": response_message.content})
            return response_message.content, messages
            
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}")
        error_msg = "Unable to fetch live data right now. Please try again later."
        messages.append({"role": "assistant", "content": error_msg})
        return error_msg, messages
