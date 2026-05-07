import random
import logging
from functools import lru_cache

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
    Returns standard PNR Object JSON format.
    """
    logger.info(f"API CALL: get_pnr_status | PNR: {pnr_number}")
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
