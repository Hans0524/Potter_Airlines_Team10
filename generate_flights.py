import random
from datetime import date, timedelta
import pandas as pd

NUM_FLIGHTS = 1000
OUTPUT_FILE = "final_flights_2.csv"

routes = ["YYZ-YVR", "YYZ-LAX", "YYZ-YOW", "YYZ-YEG", "YYZ-YHZ", "YYZ-YYC",                                              
    "YYZ-JFK",                                              # New York
    "YYZ-CUN",                                              # Cancun
    "YYZ-CDG",                                              # Paris
    "YYZ-FRA",                                              # Frankfurt
    "YYZ-NRT",                                              # Tokyo
    "YYZ-PEK",                                              # Beijing
]
 

route_base_fares = {
    "YYZ-YVR": 200, "YYZ-LAX": 300, "YYZ-YOW": 90, "YYZ-YEG": 250, "YYZ-YHZ": 150,
    "YYZ-YYC": 220, "YYZ-JFK": 180, "YYZ-CUN": 320,
    "YYZ-CDG": 650, "YYZ-FRA": 680, "YYZ-NRT": 950, "YYZ-PEK": 900,
}

route_capacity = {
    "YYZ-YVR": 150, "YYZ-LAX": 180, "YYZ-YOW": 120, "YYZ-YEG": 160, "YYZ-YHZ": 140,
    "YYZ-YYC": 150, "YYZ-JFK": 130, "YYZ-CUN": 200,
    "YYZ-CDG": 250, "YYZ-FRA": 240, "YYZ-NRT": 260, "YYZ-PEK": 260,
}

route_pop = {
    "YYZ-YVR": 1, "YYZ-LAX": 0.7, "YYZ-YOW": 0.9, "YYZ-YEG": 0.3, "YYZ-YHZ": 0.5,
    "YYZ-YYC": 0.6, "YYZ-JFK": 0.9, "YYZ-CUN": 1,
    "YYZ-CDG": 0.7, "YYZ-FRA": 0.5, "YYZ-NRT": 0.8, "YYZ-PEK": 0.4,
}

class_capacity_share = {"Economy": 0.70, "Premium": 0.20, "Business": 0.10}

def canadian_holidays(year):
    if year == 2026:
        return [date(2026, 1, 1), date(2026, 5, 18), date(2026, 7, 1),
                date(2026, 10, 12), date(2026, 12, 25)]
    elif year == 2027:
        return [date(2027, 1, 1), date(2027, 5, 24), date(2027, 7, 1),
                date(2027, 10, 11), date(2027, 12, 25)]
    else:
        return []

def random_departure_date():
    if random.random() < 0.7:
        days_out = random.randint(1, 90)
    else:
        days_out = random.randint(91, 365)
    return today + timedelta(days=days_out)

def get_season(month):
    if month in [12, 1, 2]:
        return "Winter"
    elif month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    else:
        return "Fall"

today = date.today()
holiday_list = canadian_holidays(today.year) + canadian_holidays(today.year + 1)

rows = []
for i in range(NUM_FLIGHTS):
    flight_id = f"PA{1000 + i}"

    departure_date = random_departure_date()
    day_of_week = departure_date.weekday() 
    is_weekend = day_of_week >= 5
    season = get_season(departure_date.month)
    is_holiday = departure_date in holiday_list
    days_to_departure = (departure_date - today).days
    departure_hour = random.choice([6, 8, 10, 12, 14, 16, 18, 20, 22])

    route = random.choice(routes)
    origin, destination = route.split("-")
    capacity = route_capacity[route]
    base_fare = route_base_fares[route]
    fare_class = random.choices(
        ["Economy", "Premium", "Business"], weights=[70, 20, 10], k=1)[0]
    class_capacity = max(1, int(capacity * class_capacity_share[fare_class]))

    #the occupacy generator depending on the days of departure
    if days_to_departure < 7:
        occupancy_pct = random.uniform(0.6, 0.92)
    elif days_to_departure < 30:
        occupancy_pct = random.uniform(0.3, 0.7)
    else:
        occupancy_pct = random.uniform(0.0, 0.4)

    seats_remaining = int(class_capacity * (1 - occupancy_pct))
    current_load_factor = round(1 - seats_remaining / class_capacity, 3)

    # Per-route fixed popularity, with a little day-to-day wobble (not a full reroll)

    historical_avg_route_demand = route_pop[route]

    route_popularity= round(
        min(1, route_pop[route] * random.uniform(0.9, 1.1)), 2
    )

    rows.append({
        "flight_id": flight_id,
        "route": route,
        "origin": origin,
        "destination": destination,
        "fare_class": fare_class,
        "departure_date": departure_date.isoformat(),
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "season": season,
        "is_holiday": is_holiday,
        "days_to_departure": days_to_departure,
        "departure_hour": departure_hour,
        "capacity": capacity,
        "class_capacity": class_capacity,
        "base_fare": base_fare,
        "historical_avg_route_demand": historical_avg_route_demand,
        "route_popularity": route_popularity, 
        "seats_remaining": seats_remaining,
        "current_load_factor": current_load_factor,
    })

df = pd.DataFrame(rows)
df.to_csv(OUTPUT_FILE, index=False)

print(f"Wrote {len(df)} rows to {OUTPUT_FILE}")
print(df.head(10).to_string())
