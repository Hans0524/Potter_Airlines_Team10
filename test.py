from flight import Flight
import pricing
import pricing_batch
import pandas as pd

def make_test_flight():
    return Flight(
        flight_id="TEST001",
        route="YYZ-YVR",
        origin="YYZ",
        destination="YVR",
        fare_class="Economy",
        departure_date="2026-10-10",
        day_of_week=5,
        is_weekend=True,
        season="Fall",
        is_holiday=False,
        days_to_departure=12,
        departure_hour=10,
        capacity=150,
        class_capacity=100,
        base_fare=200,
        historical_avg_route_demand=0.8,
        route_popularity=0.8,
        seats_remaining=20,
        current_load_factor=0.8
    )

#FLIGHT TEST
# Test 1: valid flight should pass validation
def test_valid_flight():
    flight = make_test_flight()

    assert flight.validate() is True

    print("PASS: valid flight")


# Test 2: load factor should be calculated correctly
def test_load_factor():
    flight = make_test_flight()

    assert flight.calculate_load_factor() == 0.8

    print("PASS: load factor calculation")


# Test 3: booking seats should update inventory
def test_booking():
    flight = make_test_flight()

    flight.book_seats(5)

    assert flight.seats_remaining == 15
    assert flight.current_load_factor == 0.85

    print("PASS: booking updates inventory")


# Test 4: booking more seats than available should fail
def test_overbooking():
    flight = make_test_flight()

    try:
        flight.book_seats(25)
        assert False, "Overbooking should raise ValueError"

    except ValueError:
        print("PASS: overbooking rejected")


# Test 5: invalid fare class should fail validation
def test_invalid_fare_class():
    flight = make_test_flight()

    flight.fare_class = "First Class"

    try:
        flight.validate()
        assert False, "Invalid fare class should raise ValueError"

    except ValueError:
        print("PASS: invalid fare class rejected")

# Test 6: capacity-related values must be integers
def test_capacity_values_require_integers():
    attributes = ["capacity", "class_capacity", "seats_remaining"]

    for attribute in attributes:
        flight = make_test_flight()
        setattr(flight, attribute, 10.5)

        try:
            flight.validate()
            assert False, f"{attribute} should require an integer"
        except ValueError:
            pass

    print("PASS: capacity values require integers")


# Test 7: base fare must be finite
def test_base_fare_requires_finite_value():
    invalid_values = [
        float("nan"),
        float("inf"),
        float("-inf")
    ]

    for value in invalid_values:
        flight = make_test_flight()
        flight.base_fare = value

        try:
            flight.validate()
            assert False, f"Invalid base fare {value} should raise ValueError"
        except ValueError:
            pass

    print("PASS: non-finite base fares rejected")


# Test 8: route popularity boundary values 0 and 1 are valid
def test_route_popularity_boundaries():
    flight = make_test_flight()

    flight.route_popularity = 0
    assert flight.validate() is True

    flight.route_popularity = 1
    assert flight.validate() is True

    print("PASS: route popularity boundaries accepted")


# Test 9: route popularity outside 0 to 1 is invalid
def test_invalid_route_popularity():
    invalid_values = [-0.1, 1.1]

    for value in invalid_values:
        flight = make_test_flight()
        flight.route_popularity = value

        try:
            flight.validate()
            assert False, f"Route popularity {value} should raise ValueError"
        except ValueError:
            pass

    print("PASS: invalid route popularity rejected")

# PRICING TEST

# Test 10: time factor boundaries
def test_time_factor():
    # 7 days or less = near departure
    assert pricing.time_factor(7) == pricing.TIME_FACTOR_NEAR

    # 8 to 21 days = mid-term
    assert pricing.time_factor(8) == pricing.TIME_FACTOR_MID
    assert pricing.time_factor(21) == pricing.TIME_FACTOR_MID

    # More than 21 days = far
    assert pricing.time_factor(22) == pricing.TIME_FACTOR_FAR

    print("PASS: time factor boundaries")


# Test 11: higher load factor should increase price
def test_capacity_increases_price():
    low_load_price = pricing.calculate_fare(
        base_fare=200,
        days_to_departure=15,
        current_load_factor=0.2,
        route_popularity=0.5,
        is_weekend=False,
        departure_date="2026-10-15",
        fare_class="Economy",
        is_holiday=False
    )

    high_load_price = pricing.calculate_fare(
        base_fare=200,
        days_to_departure=15,
        current_load_factor=0.9,
        route_popularity=0.5,
        is_weekend=False,
        departure_date="2026-10-15",
        fare_class="Economy",
        is_holiday=False
    )

    assert high_load_price > low_load_price

    print("PASS: higher load factor increases fare")


# Test 12: higher route demand should increase price
def test_demand_increases_price():
    low_demand_price = pricing.calculate_fare(
        base_fare=200,
        days_to_departure=15,
        current_load_factor=0.5,
        route_popularity=0.2,
        is_weekend=False,
        departure_date="2026-10-15",
        fare_class="Economy",
        is_holiday=False
    )

    high_demand_price = pricing.calculate_fare(
        base_fare=200,
        days_to_departure=15,
        current_load_factor=0.5,
        route_popularity=0.9,
        is_weekend=False,
        departure_date="2026-10-15",
        fare_class="Economy",
        is_holiday=False
    )

    assert high_demand_price > low_demand_price

    print("PASS: higher route demand increases fare")


# Test 13: weekend should increase price
def test_weekend_factor():
    assert pricing.weekend_factor(False) == 1.0
    assert pricing.weekend_factor(True) == pricing.WEEKEND_FACTOR
    assert pricing.weekend_factor(True) > pricing.weekend_factor(False)

    print("PASS: weekend pricing factor")


# Test 14: fare should respect floor and cap
def test_fare_bounds():
    assert pricing.clamp_fare(10) == pricing.FARE_FLOOR
    assert pricing.clamp_fare(2000) == pricing.FARE_CAP
    assert pricing.clamp_fare(200) == 200

    print("PASS: fare floor and cap")


# Test 15: invalid pricing inputs should be rejected
def test_invalid_pricing_input():
    try:
        pricing.calculate_fare(
            base_fare=200,
            days_to_departure=15,
            current_load_factor=1.5,
            route_popularity=0.5,
            is_weekend=False,
            departure_date="2026-10-15",
            fare_class="Economy",
            is_holiday=False
        )

        assert False, "Invalid load factor should raise ValueError"

    except ValueError:
        print("PASS: invalid pricing input rejected")

# BATCH PRICING TESTS

# Create a small table with multiple flights
def make_test_dataframe():
    return pd.DataFrame({
        "flight_id": ["B001", "B002", "B003"],
        "base_fare": [200, 250, 300],
        "days_to_departure": [5, 15, 30],
        "current_load_factor": [0.9, 0.5, 0.2],
        "route_popularity": [0.9, 0.5, 0.2],
        "is_weekend": [True, False, False],
        "is_holiday": [True, False, False],
        "fare_class": ["Economy", "Premium", "Business"],
        "departure_date": [
            "2026-12-20",
            "2026-10-15",
            "2026-09-20"
        ]
    })


# Test 16: batch pricing should calculate prices
# for multiple flights
def test_batch_pricing():
    flights = make_test_dataframe()

    result = pricing_batch.price_flights(flights)

    assert len(result) == 3
    assert "final_price" in result.columns
    assert result["final_price"].notna().all()

    print("PASS: batch pricing calculates multiple flights")


# Test 17: all batch prices must stay within fare limits
def test_batch_fare_bounds():
    flights = make_test_dataframe()

    result = pricing_batch.price_flights(flights)

    assert (result["final_price"] >= pricing.FARE_FLOOR).all()
    assert (result["final_price"] <= pricing.FARE_CAP).all()

    print("PASS: batch prices stay within fare bounds")


# Test 18: batch pricing should not modify original data
def test_batch_preserves_original():
    flights = make_test_dataframe()

    original = flights.copy()

    pricing_batch.price_flights(flights)

    assert flights.equals(original)

    print("PASS: batch pricing preserves original data")

def run_tests():

    print("Running Flight tests...\n")

    test_valid_flight()
    test_load_factor()
    test_booking()
    test_overbooking()
    test_invalid_fare_class()

    print("\nAll Flight tests passed!")

    print("\nRunning Pricing tests...\n")

    test_time_factor()
    test_capacity_increases_price()
    test_demand_increases_price()
    test_weekend_factor()
    test_fare_bounds()
    test_invalid_pricing_input()

    print("\nAll Pricing tests passed!")

    print("\nRunning Batch Pricing tests...\n")

    test_batch_pricing()
    test_batch_fare_bounds()
    test_batch_preserves_original()

    print("\nAll Batch Pricing tests passed!")

    print("\nALL TESTS PASSED!")

if __name__ == "__main__":
    run_tests()