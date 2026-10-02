import sqlite3
import pandas as pd

conn = sqlite3.connect("flights_2.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS flights (
        flight_id TEXT PRIMARY KEY,
        route TEXT,
        origin TEXT,
        destination TEXT, 
        fare_class TEXT,
        departure_date TEXT,
        day_of_week INTEGER,
        is_weekend INTEGER,
        season TEXT,
        is_holiday INTEGER,
        days_to_departure INTEGER,
        departure_hour INTEGER,
        capacity INTEGER,
        class_capacity INTEGER,
        base_fare REAL,
        historical_avg_route_demand REAL,
        route_popularity REAL,
        seats_remaining INTEGER,
        current_load_factor REAL
    )
""")
conn.commit()

df = pd.read_csv("final_flights_2.csv")
df.to_sql("flights", conn, if_exists="replace", index=False)

conn.close()
print("Loaded", len(df), "flights into flights.db")