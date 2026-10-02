#import
import os
import json
import requests
from getpass import getpass

MODEL = "openai/gpt-oss-20b"
PRICE_TOLERANCE = 0.01
ENV_PATH = ".env"

#loading the API key --> GROQ API
def load_key_from_env_file(): 
    if not os.path.isfile(ENV_PATH):
        return None
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None

#Collects flight and prive from flight.py,and pricing_batch.py
def explain_fare(flight, priced_row):
    API_KEY = (
        os.environ.get("GROQ_API_KEY")
        or load_key_from_env_file()
        or getpass("Enter your Groq API key: ").strip()
    )
    # gather our pricing, from get_flight, and pricing_batch.price_flights()
    facts = {
        "flight_id": flight.flight_id,
        "price_cad": round(float(priced_row["final_price"]), 2),
    }


#this is the prompt for the AI
    prompt = f"""You are explaining a flight fare to a customer. Use dollars ($) only, never any other currency symbol.

Do not write marketing copy. Explain the price like a pricing breakdown: start from the base fare, then say which factor(s) below changed it the most and by roughly how much. A factor of 1.000 means no effect on price. A factor above 1.000 increases price (e.g. 1.200 means +20%); a factor below 1.000 decreases it. If a factor is a holiday/weekend/seasonal factor and it's at 1.000, say plainly that it had no effect (e.g. "not a holiday, so no holiday surcharge").

Flight: {facts['flight_id']}
Route: {flight.route}
Fare class: {flight.fare_class}
Days to departure: {flight.days_to_departure}
Load factor: {flight.current_load_factor}
Holiday: {flight.is_holiday}
Base fare: ${flight.base_fare}
Final price: ${facts['price_cad']}

Pricing factors (each one multiplies the base fare): time={priced_row['time_factor']:.3f}, capacity={priced_row['capacity_factor']:.3f}, weekend={priced_row['weekend_factor']:.3f}, seasonal={priced_row['seasonal_factor']:.3f}, demand={priced_row['demand_factor']:.3f}, class={priced_row['class_factor']:.3f}, holiday={priced_row['holiday_factor']:.3f}

Reply with ONLY this JSON, nothing else:
{{"flight_id": "{facts['flight_id']}", "price_cad": {facts['price_cad']}, "explanation": "<2-3 sentence price breakdown identifying the biggest driver(s), in $ only>"}}
"""

    #connecting to the ai model
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,   # low = more predictable answers
                "max_tokens": 700,
            },
            timeout=45,
        )
        response.raise_for_status()          # crash loudly if something went wrong
        api_data = response.json()
    except requests.RequestException:
        print("The request failed. Check your internet or API key.")
        api_data = None


    #pulls AI result

    llm_text = None
    if api_data is not None:
        llm_text = api_data["choices"][0]["message"]["content"]

    #if AI promot produces a JSON, we need to remove the JSON

    if llm_text is not None:
        llm_text = llm_text.strip()
        lines = llm_text.splitlines()
        if lines and lines[0].startswith("```") and lines[-1] == "```":
            llm_text = "\n".join(lines[1:-1])

    #AI answer into a dictionary
    answer = None
    if llm_text is not None:
        try:
            answer = json.loads(llm_text)
        except json.JSONDecodeError:
            print("The AI didn't return valid JSON.")

    errors = check_answer(answer, facts) if answer else ["No answer to check."]

    print("\nHere is what our handy AI service bot has to say about the price — no fluff. hehe")
    print(f"Flight {facts['flight_id']}")
    print(f"Price: ${facts['price_cad']:.2f}")

    if errors:
        print("(No explanation available right now.)")
    else:
        print(answer["explanation"])

    return None if errors else answer


# checker
def check_answer(answer, facts):
    errors = []

    if answer.get("flight_id") != facts["flight_id"]:
        errors.append("Flight ID doesn't match!")

    price = answer.get("price_cad")
    if not isinstance(price, (int, float)) or abs(price - facts["price_cad"]) > PRICE_TOLERANCE:
        errors.append("Price doesn't match!")

    if not answer.get("explanation"):
        errors.append("No explanation was given.")

    return errors
