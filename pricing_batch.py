import numpy as np
import pandas as pd

import pricing

#Check all input flights for NaN, uniqueness, and valid ranges
def check_flights_table(flights):
    assert flights.notna().all().all(), "flights table contains NaN values"
    assert flights["flight_id"].is_unique, "flight_id must be unique"
    assert (flights["base_fare"] > 0).all(), "base fare must be positive"
    assert flights["current_load_factor"].between(0, 1).all(), "load factor must be between 0 and 1"
    assert flights["route_popularity"].between(0, 1).all(), "route popularity must be between 0 and 1"
    assert (flights["days_to_departure"] >= 0).all(), "days to departure must not be negative"
    assert flights["fare_class"].isin(pricing.CLASS_FACTORS).all(), \
        f"fare_class must be one of {sorted(pricing.CLASS_FACTORS)}"
    month = pd.to_numeric(flights["departure_date"].str[5:7], errors="coerce")
    assert month.between(1, 12).all(), "departure_date must be 'YYYY-MM-DD' with a month of 01-12"


def price_flights(flights):
    check_flights_table(flights)

    # Calculate on a copy so the original table stays unchanged
    baseline = flights.copy()

    # time factor, several bands -> np.select, first true condition wins
    days = baseline["days_to_departure"]
    baseline["time_factor"] = np.select(
        [days <= pricing.TIME_NEAR_DAYS, days <= pricing.TIME_MID_DAYS],
        [pricing.TIME_FACTOR_NEAR, pricing.TIME_FACTOR_MID],
        default=pricing.TIME_FACTOR_FAR,
    )

    #capacity and demand factors
    baseline["capacity_factor"] = pricing.capacity_factor(baseline["current_load_factor"])
    baseline["demand_factor"] = pricing.demand_factor(baseline["route_popularity"])

    #weekend, two-way choice -> np.where
    baseline["weekend_factor"] = np.where(baseline["is_weekend"], pricing.WEEKEND_FACTOR, 1.00)
    baseline["holiday_factor"] = np.where(baseline["is_holiday"], pricing.HOLIDAY_FACTOR, 1.00)
    baseline["class_factor"] = baseline["fare_class"].map(pricing.CLASS_FACTORS).fillna(1.00)

    #seasonal factor from the departure month 
    month = pd.to_numeric(baseline["departure_date"].str[5:7])
    baseline["seasonal_factor"] = np.select(
        [month == m for m in pricing.SEASONAL_FACTORS], list(pricing.SEASONAL_FACTORS.values()), default=pricing.DEFAULT_SEASONAL_FACTOR,
    )

    # Part 7: multiply, then enforce the fare limits and round (Session_3 Cell 15)
    baseline["raw_price"] = (
        baseline["base_fare"]
        * baseline["time_factor"]
        * baseline["capacity_factor"]
        * baseline["weekend_factor"]
        * baseline["holiday_factor"]
        * baseline["class_factor"]
        * baseline["seasonal_factor"]
        * baseline["demand_factor"]
    )
    baseline["final_price"] = np.clip(
        baseline["raw_price"], pricing.FARE_FLOOR, pricing.FARE_CAP
    ).round(2)
    return baseline
