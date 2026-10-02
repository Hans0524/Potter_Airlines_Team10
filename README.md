# Setup

This project uses [uv](https://docs.astral.sh/uv/) to manage Python and its libraries.
`pyproject.toml`, `uv.lock` and `.python-version` pin the exact environment, so one
command rebuilds it on any machine.

### 1. Create the environment

From the project folder:

```bash
uv sync
```

This creates a `.venv` folder and installs everything listed in `uv.lock`. If Python
3.12 is not installed, uv downloads it automatically.

### 2. Run

**Option A — terminal (no setup needed)**

```bash
uv run python main.py            # command-line system
uv run python dashboard_app.py   # dashboard, opens at http://localhost:8501
uv run python test.py            # tests
```

**Option B — VS Code Run button**

1. `Ctrl + Shift + P` → **Python: Select Interpreter**
2. Choose `.venv\Scripts\python.exe` in this project folder (on macOS/Linux: `.venv/bin/python`)
3. Open any file above and click ▶ Run

The interpreter only needs to be selected once per folder.


### 3.Libraries

| Library | Needed by | Purpose |
|---|---|---|
| `pandas` | `pricing_batch.py`, `sql.py`, `flight_operation.py`,`test.py`,`dashboard_app.py` | DataFrames; `pd.to_numeric` for the month lookup |
| `numpy` | `pricing_batch.py` | `np.select`, `np.where`, `np.clip` for vectorized pricing |
| `streamlit` | `dashboard_app.py` | Interactive dashboard web page |
| `plotly` | `dashboard_app.py` | Interactive charts on the dashboard |
| `sqlite3` | `sql.py`, `main.py`, `flight_operation.py` | Standard library, no installation needed |
| `requests` | `llm.py` | Sends the fare-explanation request to the Groq API |

# Flight Operations and Command-Line Interface

This section documents `flight_operation.py` and `main.py`, which connect the flight model, batch pricing calculations, and SQLite database to an interactive terminal menu. The menu also provides an AI fare explanation through `llm.explain_fare()`.

## Setup and running

Keep `main.py`, `flight_operation.py`, `flight.py`, `pricing_batch.py`, and `pricing.py` in the project directory. An existing `flights_2.db` containing the populated `flights` table must be beside `main.py`. The application reports a missing database and exits; it does not initialize one automatically.

The AI explanation feature uses the Groq API. It looks for `GROQ_API_KEY` in the environment, then in a `.env` file in the current working directory. If neither provides a key, it prompts for one with hidden input. Run the application from the project directory when using `.env`.

From the project directory, run:

```bash
python main.py
```

## `main.py`: interactive menu

`main()` opens the SQLite connection and repeatedly displays these options:

| Option                    | Action                                                                                                      |
| ------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 1. List available flights | Enter a route such as`YYZ-YVR`, or press Enter for all routes. Displays up to 10 flights, cheapest first. |
| 2. Show one flight        | Enter a flight ID to display its details, current fare, and pricing factors.                                |
| 3. Book seats             | Enter a flight ID and a positive whole number of seats. Successful bookings update the saved database.      |
| 4. Run demo               | Demonstrates database operations and overbooking rejection using an in-memory copy.                         |
| 5. Explain a fare (AI)    | Enter a flight ID to receive an AI explanation of its calculated fare.copy.                                 |
| 6. Exit                   | Leaves the menu and closes the database connection.                                                         |

The menu catches validation, input-conversion, assertion, and SQLite errors during operations, prints an error message, and allows another choice. The `if __name__ == "__main__"` block starts the menu when the file is run directly.

When option 6 is selected, `main()` retrieves the flight and calculates its fare using `pricing_batch.price_flights()`. It passes the flight and pricing results to `llm.explain_fare()`, which requests an explanation from Groq using the configured `openai/gpt-oss-20b` model.

The request includes the route, fare class, base fare, final price, and pricing factors. The model is asked to return JSON containing `flight_id`, `price_cad`, and a short explanation of the main pricing factors. Python calculates the fare; the LLM explains it.

`check_answer()` checks that the returned flight ID matches, the price is within $0.01 of the calculated fare, and an explanation is present. Request failures, invalid JSON, or failed checks cause the program to display an unavailable-explanation message while still showing the calculated flight price.

## `flight_operation.py`: flight operations

| Function                | Responsibility                                                                                                                                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `check_raw_numbers()` | Checks whole-number fields and finite numeric values before constructing a flight.                                                                                                                      |
| `make_flight()`       | Recalculates days to departure using today's date, creates a`Flight`, and validates it.                                                                                                               |
| `get_flight()`        | Retrieves one flight by ID and rejects missing or duplicate IDs.                                                                                                                                        |
| `list_flights()`      | Filters records, excludes past dates and sold-out flights, calls batch pricing, and sorts by fare, departure date, then flight ID. Returns the full ranked DataFrame while limiting the displayed rows. |
| `show_flight()`       | Displays a flight summary and its time, capacity, weekend, seasonal, and demand pricing factors. Identifies sold-out or nearly full flights.                                                            |
| `book_flight()`       | Validates the booking, updates inventory, and displays the fare before booking and the next booking's fare when seats remain.                                                                           |
| `run_demo()`          | Demonstrates INSERT, SELECT, UPDATE, DELETE, and validation checks on a temporary database copy.                                                                                                        |

Pricing is delegated to `pricing_batch.price_flights()` for both listings and bookings. Listing validation processes individual records, while the pricing calculation uses the batch module's Pandas/NumPy operations across flights.

Bookings use a SQLite transaction with `BEGIN IMMEDIATE` before reading inventory. A successful booking saves `seats_remaining`, `current_load_factor`, and `days_to_departure`, and must update exactly one row. Errors roll back the transaction. SQL values use `?` placeholders with separately supplied parameters.

## Demonstration and overbooking validation

Choose option **4** to run the demonstration. It requires at least one valid flight departing today or later with available seats.

1. Copy the saved database into memory and display the cheapest available flights.
2. Insert a temporary copy of the cheapest flight with a unique `DEMO-` ID.
3. Select that flight, book one seat, and assert that its remaining seats decreased by one.
4. Attempt to book one more seat than remains. `Flight.book_seats()` raises a `ValueError`, which the demo catches and reports.
5. Assert that the invalid booking was rejected and the saved flight record did not change.
6. Delete the temporary flight and assert that exactly one row was deleted.

The demo leaves `flights_2.db` unchanged. Normal bookings through option **3** persist inventory changes.

## Current limitations

- The active interface uses numbered menu choices. The older command examples such as `python main.py demo` in the source docstring are not implemented as argument-based commands.
- The menu supports route filtering; fare-class filtering and custom display limits are available through `list_flights()` when called from Python.
- Departure eligibility uses calendar dates rather than the departure hour or time zone.
- Booking updates flight inventory but does not create passenger, payment, or booking-history records.
- The demo uses Python assertions, so run without the `-O` option to keep these checks enabled.



# Flight Data Generation & Database Loading

## Files

| File | Purpose |
|---|---|
| `generate_flights.py` | Generates 1,000 fictional flights and writes them to `final_flights_2.csv` |
| `sql.py` | Creates the `flights` table in `flights_2.db` and loads the CSV into it |

## Data Generation (`generate_flights.py`)

Fixed per-route reference tables combined with randomized per-flight details.

Route tables: `route_base_fares` (starting fare, $90–$950), `route_capacity` (120–260 seats), `route_pop` (0–1 baseline popularity), and `class_capacity_share` (Economy 70% / Premium 20% / Business 10%).

### Per-flight generation

| Field | Rule |
|---|---|
| `flight_id` | Sequential, PA1000–PA1999 |
| `departure_date` | 70% within 90 days, 30% within 91–365 days |
| `day_of_week`, `is_weekend`, `season` | Derived from departure date |
| `is_holiday` | Five fixed Canadian holidays, 2026–2027 |
| `route`, `fare_class` | Random; fare class weighted 70/20/10 |
| `class_capacity` | Route capacity × class share, minimum 1 seat |
| `route_popularity` | Baseline popularity with ±10% random variation, capped at 1.0 |

### Occupancy and capacity

Occupancy is applied to `class_capacity`, not total aircraft capacity.

| Days to departure | Occupancy |
|---|---|
| < 7 | 60%–92% |
| 7–29 | 30%–70% |
| 30+ | 0%–40% |

`seats_remaining` and `current_load_factor` are derived from the generated occupancy.

## Output Schema (`final_flights_2.csv`)

| Column | Type | Description |
|---|---|---|
| `flight_id` | text | Unique flight ID, e.g. PA1042 |
| `route` / `origin` / `destination` | text | Route and airport codes |
| `fare_class` | text | Economy / Premium / Business |
| `departure_date` | text | YYYY-MM-DD |
| `day_of_week` | int | 0–6 |
| `is_weekend` | bool | Weekend indicator |
| `season` | text | Winter / Spring / Summer / Fall |
| `is_holiday` | bool | Holiday indicator |
| `days_to_departure` | int | Days until departure |
| `departure_hour` | int | 6–22 |
| `capacity` | int | Total aircraft capacity |
| `class_capacity` | int | Capacity allocated to the fare class |
| `base_fare` | real | Route starting fare |
| `historical_avg_route_demand` | real | Fixed route popularity baseline |
| `route_popularity` | real | Baseline popularity with random variation |
| `seats_remaining` | int | Unsold seats in the fare class |
| `current_load_factor` | real | Fraction of class capacity sold |

## Database Loading (`sql.py`)

Creates a `flights` table matching the CSV schema and loads the data using:

```python
df.to_sql("flights", conn, if_exists="replace")
```

`flight_id` is the primary key. Re-running both scripts replaces the existing table rather than appending records.

## Known Limitations

- Occupancy and demand figures are synthetic and do not represent real booking data.
- Holiday dates are hardcoded for 2026–2027.
- `class_capacity` has a minimum of 1 seat, so small allocations may not exactly match the stated class share.


# Flight Class

The `Flight` class represents one flight record in the Potter Airlines system. It stores flight information, seat inventory, fare inputs, and demand data. It also checks that the values are valid before they are used by other parts of the project.

## Validation

The main validation is handled by `Flight.validate()`. It checks important business rules and data consistency, including:

| Field / Rule | Validation |
| :---- | :---- |
| Fare class | Must be `Economy`, `Premium`, or `Business` |
| Departure date | Must follow `YYYY-MM-DD` format |
| Day of week | Must be between 0 and 6 and match the departure date |
| Capacity | Must be a positive integer |
| Class capacity | Must be a positive integer and cannot exceed total capacity |
| Seats remaining | Must be an integer between 0 and `class_capacity` |
| Base fare | Must be positive and finite |
| Route popularity | Must be between 0 and 1, inclusive |
| Load factor | Must be between 0 and 1 and match the seat inventory |
| Route | Must match the origin and destination |

These checks help prevent invalid flight data from reaching the pricing and database operations.

## Load Factor and Seat Inventory

Load factor is calculated at the fare-class level:

```py
load_factor = 1 - (seats_remaining / class_capacity)
```

`class_capacity` is used instead of total aircraft `capacity` because `seats_remaining` also refers to one fare class. This keeps both values at the same level.

The class also provides several helper methods:

- `calculate_load_factor()` calculates how full the fare class is.  
- `available_seat_ratio()` calculates the proportion of seats still available.  
- `is_nearly_full()` returns `True` when the load factor reaches a selected threshold.  
- `book_seats()` updates the remaining seats and recalculates the load factor.  
- `to_dict()` converts the flight object into a dictionary for use with other parts of the system.  
- `summary()` returns a short readable description of the flight.

## Design Notes

`route_popularity` uses the range `0 <= p <= 1`, which is consistent with the pricing module. A value of 0 is valid and represents the lowest route popularity.

Capacity-related fields are required to be whole numbers because they represent physical seats. `base_fare` also rejects `NaN` and infinite values to avoid invalid pricing inputs.

`historical_avg_route_demand` is stored and validated for possible analysis, but it is not currently used in the pricing formula.

`book_seats()` updates the `Flight` object in memory. Database updates are handled separately by the database and flight-operation modules.

# Pricing Module

**Owner:** Zidi (Hans) Gao · **Files:** `pricing.py` (one flight), `pricing_batch.py` (a whole table)

Everything else in the system asks this module for a fare rather than computing one
itself, so there is exactly one pricing rule in the project.


## The pricing model

A fare is the base fare multiplied by seven independent factors, then held inside a
floor and a cap:

```
fare = base_fare
     × time_factor        (how soon is departure)
     × capacity_factor    (how full is the cabin)
     × weekend_factor     (Saturday/Sunday departure)
     × holiday_factor     (festive period)
     × seasonal_factor    (which month)
     × demand_factor      (how popular is the route)
     × class_factor       (Economy / Premium / Business)

fare = min(max(fare, 45.00), 1500.00)      then rounded to 2 decimals
```

Multiplicative rather than additive because each effect is a *percentage* adjustment: a
35% last-minute premium should be worth more on a $900 long-haul seat than on a $120
regional hop.

| Factor | Rule | Value | Reasoning |
|---|---|---|---|
| **Time** | ≤ 7 days | **1.35** | Late bookers are usually business travellers with no flexibility |
| | 8–21 days | **1.10** | Mixed demand |
| | > 21 days | **1.00** | Baseline; early bookers are price-driven leisure travellers |
| **Capacity** | `1 + 0.45 × load_factor` | 1.00 → 1.45 | Scarcity pricing. Continuous, so there is no price cliff at an arbitrary threshold |
| **Weekend** | `is_weekend` | **1.08** | Leisure demand concentrates on Sat/Sun departures |
| **Holiday** | `is_holiday` | **1.20** | Christmas, New Year, Thanksgiving — demand spikes and is inelastic |
| **Seasonal** | month lookup | 0.95 → 1.20 | Jul/Aug/Dec peak, Jan/Feb/Oct/Nov trough |
| **Demand** | `0.9 + 0.3 × route_popularity` | 0.90 → 1.20 | Unwanted routes get a 10% discount, the most popular a 20% premium |
| **Class** | Economy / Premium / Business | 1.00 / 1.20 / 1.50 | Cabin willingness-to-pay differs by a roughly fixed multiple |

All values are named constants at the top of `pricing.py`, so they can be retuned in one
place without reading any function body.

`FARE_FLOOR = 45.00` protects against selling below marginal cost. `FARE_CAP = 1500.00`
is a reputational guard — an uncapped multiplicative model can produce headline-grabbing
fares during a demand spike. On the current 1000-flight dataset the cap binds on 57
flights and the floor on none.

## Worked example

`base_fare = 200`, 30 days out, cabin 50% sold, `route_popularity = 0.50`, weekday,
2026-03-10, Economy, not a holiday.

| Step | Factor | Running fare |
|---|---|---|
| start | — | 200.00 |
| time (30 days > 21) | × 1.00 | 200.00 |
| capacity (1 + 0.45 × 0.50) | × 1.225 | 245.00 |
| weekend (weekday) | × 1.00 | 245.00 |
| holiday (no) | × 1.00 | 245.00 |
| seasonal (March) | × 1.00 | 245.00 |
| demand (0.9 + 0.3 × 0.50) | × 1.05 | 257.25 |
| class (Economy) | × 1.00 | 257.25 |
| clamp to [45, 1500] | — | **257.25** |

Change only the cabin to Business and the fare becomes **385.88**. Change only the
holiday flag and it becomes **308.70**.

## Input fields

Both `price_single(flight)` and `price_flights(flights)` expect these fields, matching the
column names in the team database:

| Field | Type | Valid range |
|---|---|---|
| `base_fare` | number | > 0 |
| `days_to_departure` | integer | ≥ 0 |
| `current_load_factor` | float | 0.0 – 1.0 |
| `route_popularity` | float | 0.0 – 1.0 |
| `is_weekend` | 0/1 or bool | — |
| `is_holiday` | 0/1 or bool | — |
| `departure_date` | string | `YYYY-MM-DD` |
| `fare_class` | string | `Economy` / `Premium` / `Business` |

`current_load_factor` is read from the database rather than recomputed from seats, so the
pricing module has no opinion about how the cabin was filled.

`price_flights` returns a new DataFrame with one column per factor plus `raw_price` and
`final_price`, which lets the CLI and the web page show *why* a fare is what it is, not
just the number.

## Testing and Validation

The project includes `test.py` to verify the core flight operations and dynamic pricing logic. The tests are organized into three main areas:

### Flight Tests
The Flight tests validate the main business rules of the `Flight` class, including:
- validation of valid and invalid flight data
- load factor calculations
- seat inventory updates after booking
- rejection of bookings that exceed the number of available seats
- rejection of invalid fare classes
- validation that capacity, class capacity, and seats remaining are whole-number integers
- rejection of non-finite base fares, including NaN and positive/negative infinity
- validation of route popularity boundaries from 0 to 1

### Pricing Tests
The pricing tests verify that the pricing model behaves consistently with its intended business logic. They check:
- pricing factor boundaries based on days to departure
- higher load factors result in higher fares, holding other factors constant
- higher route popularity results in higher fares, holding other factors constant
- weekend, holiday, and fare-class pricing factors
- enforcement of minimum and maximum fare limits
- rejection of invalid pricing inputs

### Batch Pricing Tests
The batch pricing tests validate the Pandas/NumPy-based pricing process across multiple flights. They confirm that:
- prices are successfully calculated for multiple flights
- all calculated fares remain within the defined fare bounds
- the original input DataFrame is not modified during pricing

### Edge Case
One important edge case tested is overbooking. If a booking request exceeds the number of seats remaining in the selected fare class, the system raises a `ValueError` and prevents the inventory from becoming negative.

### Running the Tests

From the project directory, run:

```bash
python3 test.py
```
# Team

| Component | Files | Owner |
|---|---|---|
| Main program and workflow | `main.py`, `flight_operation.py` | `David Wang` |
| Flight class | `flight.py` | `Xinyue Li` |
| Pricing engine | `pricing.py`, `pricing_batch.py` | `Zidi Gao` |
| Database and data generation | `sql.py`, `generate_flights.py`, `flights_2.db` | `Andrew Batmunkh` |
| Testing | `test.py` | |
| Dashboard | `dashboard_app.py`, `.streamlit/` | `Zidi Gao`|
| AI fare explanation | `llm.py` | `Andrew Batmunkh` |

## Use of AI Tools
We used Claude and ChatGPT to help debug our code, review parts of the project, understand course concepts, and draft documentation. We reviewed their suggestions and tested all submitted code. Our team can explain how the code works.
