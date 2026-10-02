#load factor calculated in Class flight
#Only considering Class Capacity rather than Capacity??
#def is_nearly_full(self, threshold=0.85): , what does the boolean return used to do?

#Levels and Holidays factors
#Constant Factors
#Time Factors
TIME_FACTOR_NEAR = 1.35     # Within 7 days
TIME_FACTOR_MID = 1.10      # 8 to 21 days 
TIME_FACTOR_FAR = 1.00      # More than 21 days
TIME_NEAR_DAYS = 7          # Cutoff for the near-term period
TIME_MID_DAYS = 21          # Cutoff for the mid-term period


#Class CAPACITY effect: the fuller the flight, the higher the price
#Class CAPACITY FACTOR = 1 + 0.45 * current_load_factor
CAPACITY_SENSITIVITY = 0.45

#Weekend factor (Saturday/Sunday, taken from Andrew's is_weekend column)
WEEKEND_FACTOR = 1.08

#Holiday factor: Festive periods (Christmas, New Year, Thanksgiving, etc.) have higher demand and prices
HOLIDAY_FACTOR = 1.20

# Demand effect: the more popular the route, the higher the price
# DEMAND FACTOR = 0.9 + 0.3 * route_popularity 
DEMAND_INTERCEPT = 0.9
DEMAND_SLOPE = 0.3

#Class factors: More expensive classes have higher base fares
CLASS_FACTORS = {
    "Economy": 1.0,
    "Premium": 1.2,
    "Business": 1.5,
}

#Seasonal effect 
SEASONAL_FACTORS = {
    1:  0.95,
    2:  0.95,  
    3:  1.00,   
    4:  1.05, 
    5:  1.00,  
    6:  1.15,  
    7:  1.20,  
    8:  1.20, 
    9:  1.10,  
    10: 0.95,  
    11: 0.95,   
    12: 1.20, 
}
DEFAULT_SEASONAL_FACTOR = 1.0 #Factor for abnormal months

#Fare Interval
FARE_FLOOR = 45.0
FARE_CAP = 1500.0

#Check input flight format
def check_flight(base_fare, current_load_factor, route_popularity):
    if base_fare <= 0:
        raise ValueError(f"Base fare must be positive. Got {base_fare}.")
    if not (0 <= current_load_factor <= 1):
        raise ValueError(f"Load factor must be between 0 and 1. Got {current_load_factor}.")
    if not (0 <= route_popularity <= 1):
        raise ValueError(f"Route popularity must be between 0 and 1. Got {route_popularity}.")

def check_date(departure_date):
    #Check if the departure date is in the correct format (YYYY-MM-DD)
    if len(departure_date) != 10 or departure_date[4] != '-' or departure_date[7] != '-':
        raise ValueError(f"Departure date must be in YYYY-MM-DD format. Got {departure_date!r}.")
    month = int(departure_date[5:7])
    if month < 1 or month > 12:
        raise ValueError(f"Month must be between 1 and 12. Got {departure_date!r}.")

# Time factor
def time_factor(days_to_departure):
    if days_to_departure <= TIME_NEAR_DAYS:
        return TIME_FACTOR_NEAR
    elif days_to_departure <= TIME_MID_DAYS:
        return TIME_FACTOR_MID
    else:
        return TIME_FACTOR_FAR

# Capacity factor
def capacity_factor(current_load_factor):
    return 1 + CAPACITY_SENSITIVITY * current_load_factor

#Demand factor
def demand_factor(route_popularity):
    return DEMAND_INTERCEPT + DEMAND_SLOPE * route_popularity

# Class factor
def class_factor(fare_class):
    return CLASS_FACTORS.get(fare_class, 1.0)  # Default to Economy if class not found

# Weekend/Weekday
def weekend_factor(is_weekend):
    if is_weekend:    #Weekend
        return WEEKEND_FACTOR
    else:   #Weekday
        return 1.0

#Holiday factor
def holiday_factor(is_holiday):
    if is_holiday:    #Holiday
        return HOLIDAY_FACTOR
    else:   #Non-Holiday
        return 1.0

#Seasonal factor
def seasonal_factor(departure_date):
    month = int(departure_date[5:7])
    return SEASONAL_FACTORS.get(month, DEFAULT_SEASONAL_FACTOR)

#lower bound / upper bound
def clamp_fare(fare):
    if fare < FARE_FLOOR:
        return FARE_FLOOR
    if fare > FARE_CAP:
        return FARE_CAP
    return fare

#Calculate fare
def calculate_fare(base_fare, days_to_departure, current_load_factor,
                   route_popularity, is_weekend, departure_date, fare_class, is_holiday):
    check_flight(base_fare, current_load_factor, route_popularity)
    check_date(departure_date)

    fare = base_fare
    fare *= time_factor(days_to_departure)
    fare *= capacity_factor(current_load_factor)
    fare *= weekend_factor(is_weekend)
    fare *= holiday_factor(is_holiday)
    fare *= seasonal_factor(departure_date)
    fare *= demand_factor(route_popularity)
    fare *= class_factor(fare_class)
    fare = clamp_fare(fare)
    assert FARE_FLOOR <= fare <= FARE_CAP, f"clamp_fare failed: {fare}"
    return round(fare, 2)

# Conventient wrapper to calculate fare from a flight record 
def price_single(flight):
    return calculate_fare(
        flight["base_fare"],
        flight["days_to_departure"],
        flight["current_load_factor"],
        flight["route_popularity"],
        flight["is_weekend"],
        flight["departure_date"],
        flight["fare_class"],
        flight["is_holiday"]
    )