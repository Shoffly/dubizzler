import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import time
import hashlib
import re

def extract_car_brand(car_name):
    """Extract the car brand from the car name."""
    if car_name == "N/A":
        return "N/A"

    # Common car brands
    brands = [
        "Toyota", "Honda", "Ford", "Chevrolet", "Nissan", "Hyundai", "Kia", "Mazda", 
        "Volkswagen", "BMW", "Mercedes", "Audi", "Lexus", "Jeep", "Subaru", "Volvo",
        "Mitsubishi", "Suzuki", "Peugeot", "Renault", "Fiat", "Citroen", "Opel",
        "Skoda", "Seat", "Land Rover", "Range Rover", "Jaguar", "Porsche", "Ferrari",
        "Lamborghini", "Maserati", "Bentley", "Rolls Royce", "Mini", "Infiniti",
        "Acura", "Cadillac", "Lincoln", "Buick", "GMC", "Dodge", "Chrysler", "Jeep",
        "Ram", "Tesla", "BYD", "Chery", "Geely", "MG", "Proton", "Daihatsu", "Isuzu"
    ]

    # Check if any brand is in the car name
    for brand in brands:
        if brand.lower() in car_name.lower():
            return brand

    # If no brand is found, return the first word as the brand
    return car_name.split()[0]

def parse_listing_time(listing_time):
    """Convert listing time text (e.g., '35 minutes ago', '2 days ago') to days on website."""
    if listing_time == "N/A":
        return "N/A"

    # Extract the number and unit from the listing time
    match = re.match(r'(\d+)\s+(\w+)\s+ago', listing_time)
    if not match:
        return "N/A"

    value, unit = match.groups()
    value = int(value)

    # Convert to days
    if 'minute' in unit:
        return round(value / (24 * 60), 2)  # Convert minutes to days
    elif 'hour' in unit:
        return round(value / 24, 2)  # Convert hours to days
    elif 'day' in unit:
        return value  # Already in days
    elif 'week' in unit:
        return value * 7  # Convert weeks to days
    elif 'month' in unit:
        return value * 30  # Approximate months to days
    elif 'year' in unit:
        return value * 365  # Approximate years to days
    else:
        return "N/A"

def scrape_dubizzle_cars(dealer_url, dealer_code):
    # Set a user agent to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Send a GET request to the URL
    print(f"Scraping {dealer_url}...")
    response = requests.get(dealer_url, headers=headers)

    # Check if the request was successful
    if response.status_code != 200:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return []

    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all car listing items
    car_listings = soup.select('li.undefined[aria-label="Listing"]')

    # List to store car data
    cars_data = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Base URL for listings
    base_url = "https://www.dubizzle.com.eg"

    for car in car_listings:
        # Extract car name
        car_name_elem = car.select_one('p._21aa22f1')
        car_name = car_name_elem.text.strip() if car_name_elem else "N/A"

        # Extract car brand
        car_brand = extract_car_brand(car_name)

        # Extract price
        price_elem = car.select_one('span.bb146142')
        price = price_elem.text.strip() if price_elem else "N/A"

        # Extract kilometrage and year
        kilometrage_elem = car.select_one('span._3e1113f0:not(._600acaba)')
        kilometrage = kilometrage_elem.text.strip() if kilometrage_elem else "N/A"

        year_elem = car.select_one('span._3e1113f0._600acaba')
        year = year_elem.text.strip() if year_elem else "N/A"

        # Extract listing time
        time_elem = car.select_one('span[aria-label="Creation date"]')
        listing_time = time_elem.text.strip() if time_elem else "N/A"

        # Calculate days on website
        days_on_website = parse_listing_time(listing_time)

        # Extract location
        location_elem = car.select_one('span._61e1298c')
        location = location_elem.text.strip() if location_elem else "N/A"

        # Extract listing URL
        link_elem = car.select_one('a')
        listing_url = base_url + link_elem['href'] if link_elem and 'href' in link_elem.attrs else "N/A"

        # Create a unique ID for the car based on its details
        # This will help identify if a car was previously listed
        car_details = f"{dealer_code}_{car_name}_{year}_{kilometrage}"
        car_id = hashlib.md5(car_details.encode()).hexdigest()

        # Add data to our list
        cars_data.append({
            'car_id': car_id,
            'dealer_code': dealer_code,
            'created at': current_time,
            'Car Brand': car_brand,
            'Car Name': car_name,
            'Price': price,
            'Kilometrage': kilometrage,
            'Year': year,
            'Location': location,
            'Listed': listing_time,
            'Days on Website': days_on_website,
            'Listing URL': listing_url
        })

    return cars_data

def main():
    # Set up Google Sheets API
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    try:
        credentials = Credentials.from_service_account_file('sheet_access.json', scopes=scopes)
        gc = gspread.authorize(credentials)

        # Open the spreadsheet
        spreadsheet = gc.open('Dealers Dubizzle Scraper')

        # Get the dealers tab
        dealers_sheet = spreadsheet.worksheet('dealers')
        # Define expected headers for dealers sheet
        dealer_headers = ['Code', 'Dealer', 'Link']
        dealers_data = dealers_sheet.get_all_records(expected_headers=dealer_headers)

        # Get the database tab
        database_sheet = spreadsheet.worksheet('database')

        # Define expected headers for database sheet
        db_headers = ['car_id', 'dealer_code', 'created at', 'Car Brand', 'Car Name', 'Price', 
                     'Kilometrage', 'Year', 'Location', 'Listed', 'Days on Website', 'Listing URL', 'status']

        # Get existing car IDs to check for new vs. existing cars
        existing_data = database_sheet.get_all_records(expected_headers=db_headers)
        existing_car_ids = set()
        if existing_data:
            existing_car_ids = {row.get('car_id', '') for row in existing_data if row.get('car_id')}

        # Ensure headers exist in the database sheet
        headers = db_headers
        if not database_sheet.get_all_values():
            database_sheet.append_row(headers)

        # Track total cars added
        total_cars_added = 0
        new_cars_added = 0

        # Loop through each dealer
        for dealer in dealers_data:
            dealer_code = dealer['Code']
            dealer_name = dealer['Dealer']
            dealer_url = dealer['Link']

            print(f"\nProcessing dealer: {dealer_name} (Code: {dealer_code})")

            # Scrape cars for this dealer
            cars = scrape_dubizzle_cars(dealer_url, dealer_code)

            if not cars:
                print(f"No car listings found for {dealer_name}.")
                continue

            print(f"Found {len(cars)} car listings for {dealer_name}.")

            # Prepare data for Google Sheets for this dealer only
            rows_to_add = []
            dealer_new_cars = 0

            for car in cars:
                # Check if this car is new or existing
                if car['car_id'] in existing_car_ids:
                    car['status'] = 'existing'
                else:
                    car['status'] = 'new'
                    dealer_new_cars += 1

                row = [car.get(header, '') for header in headers]
                rows_to_add.append(row)

            # Add this dealer's data to the database sheet
            database_sheet.append_rows(rows_to_add)
            print(f"Added {len(rows_to_add)} car listings for {dealer_name} to the database tab.")
            print(f"New cars: {dealer_new_cars}, Existing cars: {len(rows_to_add) - dealer_new_cars}")

            total_cars_added += len(rows_to_add)
            new_cars_added += dealer_new_cars

            # Add a small delay to avoid overwhelming the server
            time.sleep(2)

        print(f"\nTotal: Added {total_cars_added} car listings to the database tab.")
        print(f"New cars: {new_cars_added}, Existing cars: {total_cars_added - new_cars_added}")

        # Also save all data to CSV as a backup
        if total_cars_added > 0:
            # Get all data from the database sheet
            all_data = database_sheet.get_all_records(expected_headers=db_headers)
            df = pd.DataFrame(all_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dubizzle_cars_{timestamp}.csv"
            df.to_csv(filename, index=False)
            print(f"Data also saved to {filename}")
        else:
            print("No car listings found for any dealer.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
