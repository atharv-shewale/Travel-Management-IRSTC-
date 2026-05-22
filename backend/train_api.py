import random
import logging
from functools import lru_cache
from database import save_booking, get_booking

logger = logging.getLogger(__name__)

@lru_cache(maxsize=100)
def search_trains(source: str, destination: str, date: str):
    """
    Mock API call to search trains between two stations.
    Uses lru_cache to cache frequent identical searches.
    """
    logger.info(f"API CALL: search_trains | Source: {source}, Dest: {destination}, Date: {date}")
    
    # Dynamic Train Generation Logic
    # Seed the random generator so the same route/date returns consistent results
    seed_str = f"{source.lower()}-{destination.lower()}-{date}"
    random.seed(seed_str)
    
    train_types = [
        ("Rajdhani Express", ["1A", "2A", "3A"]),
        ("Shatabdi Express", ["CC", "EC"]),
        ("Vande Bharat", ["CC", "EC"]),
        ("Garib Rath", ["3A", "CC"]),
        ("Duronto Express", ["1A", "2A", "3A", "SL"]),
        ("Superfast Express", ["2A", "3A", "SL", "2S"]),
        ("Mail/Express", ["2A", "3A", "SL", "2S", "UR"])
    ]
    
    num_trains = random.randint(2, 6)
    trains = []
    
    for _ in range(num_trains):
        t_type, classes = random.choice(train_types)
        train_num = str(random.randint(11000, 22999))
        name = f"{source[:3].upper()}-{destination[:3].upper()} {t_type}"
        
        dep_hour = random.randint(0, 23)
        dep_min = random.choice([0, 10, 15, 30, 45, 50])
        duration_hrs = random.randint(3, 36)
        duration_mins = random.choice([0, 10, 15, 20, 30, 40, 45, 50])
        
        arr_hour = (dep_hour + duration_hrs) % 24
        arr_min = (dep_min + duration_mins) % 60
        
        fare = random.randint(300, 3500)
        availability_states = [
            f"AVAILABLE {random.randint(1, 150)}", 
            f"RAC {random.randint(1, 50)}", 
            f"WL {random.randint(1, 100)}"
        ]
        availability = random.choices(availability_states, weights=[60, 20, 20])[0]
        
        trains.append({
            "train_number": train_num,
            "train_name": name,
            "departure_time": f"{dep_hour:02d}:{dep_min:02d}",
            "arrival_time": f"{arr_hour:02d}:{arr_min:02d}",
            "duration": f"{duration_hrs}h {duration_mins:02d}m",
            "classes": classes,
            "fare_estimate": fare,
            "availability": availability
        })
    
    # Reset seed so it doesn't affect other random calls
    random.seed()
    
    return {
        "status": "success",
        "data": trains
    }

def check_availability(train_number: str, date: str, travel_class: str):
    """
    Mock API call to check seat availability.
    """
    logger.info(f"API CALL: check_availability | Train: {train_number}, Date: {date}, Class: {travel_class}")
    status_options = ["AVAILABLE 10", "RAC 24", "WL 15", "AVAILABLE 2"]
    
    return {
        "status": "success",
        "data": {
            "train_number": train_number,
            "date": date,
            "class": travel_class,
            "availability": random.choice(status_options)
        }
    }

def get_pnr_status(pnr_number: str):
    """
    Mock API call to check PNR status.
    First looks up SQLite database for active bookings, then falls back to randomized values.
    """
    logger.info(f"API CALL: get_pnr_status | PNR: {pnr_number}")
    
    try:
        db_booking = get_booking(pnr_number)
        if db_booking:
            logger.info(f"PNR Match found in SQLite: {pnr_number}")
            return {
                "status": "success",
                "data": {
                    "pnr_number": pnr_number,
                    "status": db_booking.get("status", "CONFIRMED"),
                    "train_number": db_booking.get("train_number"),
                    "train_name": db_booking.get("train_name"),
                    "date": db_booking.get("date"),
                    "travel_class": db_booking.get("travel_class"),
                    "passenger": db_booking.get("passenger_name"),
                    "age": db_booking.get("age"),
                    "coach": db_booking.get("coach"),
                    "berth": db_booking.get("berth"),
                    "passengers": [
                        {
                            "name": db_booking.get("passenger_name"),
                            "age": db_booking.get("age"),
                            "berth": f"{db_booking.get('coach')}-{db_booking.get('berth')}",
                            "status": db_booking.get("status", "CONFIRMED")
                        }
                    ]
                }
            }
    except Exception as e:
        logger.error(f"Error checking PNR in DB: {e}")

    # Fallback to randomized values if PNR not in database
    statuses = ["CNF", "RAC", "WL"]
    status = random.choice(statuses)
    
    passengers = []
    num_passengers = random.randint(1, 4)
    for _ in range(num_passengers):
        if status == "CNF":
            berth = f"B{random.randint(1,5)}-{random.randint(1,72)}"
        else:
            berth = "-"
        passengers.append({"berth": berth, "status": status})
        
    return {
        "status": "success",
        "data": {
            "pnr_number": pnr_number,
            "status": status,
            "passengers": passengers
        }
    }

def book_ticket(train_number: str, date: str, travel_class: str, passenger_name: str, age: int):
    """
    Mock API call to book a ticket and persist it in SQLite database.
    """
    logger.info(f"API CALL: book_ticket | Train: {train_number}, Date: {date}, Class: {travel_class}, Passenger: {passenger_name}")
    
    # Generate a mock PNR
    pnr = "".join([str(random.randint(0, 9)) for _ in range(10)])
    coach = f"B{random.randint(1, 5)}"
    berth = random.randint(1, 72)
    
    # Construct booking payload
    booking_payload = {
        "pnr_number": pnr,
        "train_number": train_number,
        "train_name": f"EXP #{train_number}",
        "date": date,
        "travel_class": travel_class,
        "passenger": passenger_name,
        "age": age,
        "status": "CONFIRMED",
        "coach": coach,
        "berth": berth
    }
    
    # Persist in Database
    try:
        save_booking(booking_payload)
        logger.info(f"Successfully persisted booking to SQLite: {pnr}")
    except Exception as e:
        logger.error(f"Database save failed for PNR {pnr}: {e}")
        
    return {
        "status": "success",
        "message": "Ticket booked successfully!",
        "data": booking_payload
    }

def get_itinerary_suggestions(destination: str, days: int = 2):
    """
    Retrieve tourist attractions, food recommendations, and a day-by-day plan for a city.
    """
    logger.info(f"API CALL: get_itinerary_suggestions | Dest: {destination}, Days: {days}")
    dest_lower = destination.lower()
    
    itineraries = {
        "delhi": {
            "highlights": ["Red Fort", "Qutub Minar", "India Gate", "Lotus Temple", "Chandni Chowk"],
            "foods": ["Chole Bhature", "Paranthas of Chandni Chowk", "Butter Chicken", "Jalebi"],
            "tips": "Use the Delhi Metro for fastest transit. Best visited from October to March.",
            "schedule": [
                {"day": 1, "title": "Historic Old Delhi Tour", "activities": ["Morning exploration of Red Fort", "Rickshaw ride through Chandni Chowk", "Spiced lunch at Karim's", "Afternoon visit to Jama Masjid"]},
                {"day": 2, "title": "Modern New Delhi Sightseeing", "activities": ["Drive past India Gate and Parliament House", "Explore Humayun's Tomb", "Peaceful walk at Lotus Temple", "Evening shopping at Connaught Place"]}
            ]
        },
        "mumbai": {
            "highlights": ["Gateway of India", "Marine Drive", "Siddhivinayak Temple", "Elephanta Caves", "Colaba Causeway"],
            "foods": ["Vada Pav", "Pav Bhaji", "Bhel Puri", "Bombay Sandwich", "Irani Chai"],
            "tips": "Try local trains for non-peak hours. Best time is November to February.",
            "schedule": [
                {"day": 1, "title": "Colonial Charm & Marine Vibes", "activities": ["Sunrise at Gateway of India", "Walk through Colaba Heritage streets", "Ferry to Elephanta Caves", "Sunset stroll and street food at Marine Drive"]},
                {"day": 2, "title": "Cultural Icons & Markets", "activities": ["Morning visit to Siddhivinayak Temple", "Dharavi tour / Dhobi Ghat photo-op", "Shopping at Crawford Market", "Dinner at iconic Cafe Leopold"]}
            ]
        },
        "jaipur": {
            "highlights": ["Hawa Mahal", "Amber Fort", "City Palace", "Jantar Mantar", "Chokhi Dhani"],
            "foods": ["Dal Baati Churma", "Pyaaz Kachori", "Gatte ki Sabji", "Lassi at Lassiwala"],
            "tips": "Hire an authorized tour guide at Amber Fort. Best visited in Winter.",
            "schedule": [
                {"day": 1, "title": "Forts & Royal Grandeur", "activities": ["Morning ascent to Amber Fort", "Photo stop at Jal Mahal (Water Palace)", "Explore Hawa Mahal (Palace of Winds)", "Evening cultural experience at Chokhi Dhani"]},
                {"day": 2, "title": "Palaces & Local Craft Bazaars", "activities": ["Explore City Palace Museum", "See astronomical instruments at Jantar Mantar", "Shopping for block prints & gems at Johri Bazaar", "Royal dinner inside Amer Fort"]}
            ]
        }
    }
    
    # Fallback default itinerary
    default_itinerary = {
        "highlights": ["Historic Architecture", "Local Landmarks", "Cultural Museum", "Central Bazaar"],
        "foods": ["Local Traditional Delicacies", "Popular Regional Desserts", "Street Food Specials"],
        "tips": "Check local weather and operational hours for attractions beforehand.",
        "schedule": [
            {"day": 1, "title": "Sights & Heritage Discovery", "activities": ["Morning walking tour of the prominent heritage circle", "Lunch at a well-reviewed traditional eatery", "Afternoon exploring local museums and monuments"]},
            {"day": 2, "title": "Shopping Bazaars & Sunset Views", "activities": ["Explore local handicraft and textile markets", "Try famous street food snacks and beverages", "Enjoy sunset from a scenic overlook"]}
        ]
    }
    
    matched_data = default_itinerary
    matched_city = destination.capitalize()
    
    for city, data in itineraries.items():
        if city in dest_lower or dest_lower in city:
            matched_data = data
            matched_city = city.capitalize()
            break
            
    if days == 1:
        matched_data = matched_data.copy()
        matched_data["schedule"] = matched_data["schedule"][:1]
        
    return {
        "status": "success",
        "destination": matched_city,
        "data": matched_data
    }

