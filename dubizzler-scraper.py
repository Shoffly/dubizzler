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

def scrape_hatla2ee_cars(dealer_url, dealer_code):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print(f"Scraping {dealer_url}...")
    response = requests.get(dealer_url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    car_listings = soup.select('div.newCarListUnit_contain')
    cars_data = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for car in car_listings:
        # Extract car name and details
        car_header = car.select_one('div.newCarListUnit_header a')
        car_name = car_header.text.strip() if car_header else "N/A"

        # Extract car brand
        car_brand = extract_car_brand(car_name)

        # Extract price and format it to match Dubizzle's format
        price_elem = car.select_one('div.main_price a')
        price = "N/A"
        if price_elem:
            # Remove any whitespace and "EGP" from the price
            price_text = price_elem.text.strip()
            # Extract numbers and format them
            price_numbers = ''.join(filter(str.isdigit, price_text))
            if price_numbers:
                # Format as "EGP X,XXX,XXX"
                try:
                    price_value = int(price_numbers)
                    price = f"EGP {price_value:,}"
                except ValueError:
                    price = "N/A"

        # Extract kilometrage and other details
        meta_tags = car.select('span.newCarListUnit_metaTag')
        kilometrage = "N/A"
        location = "N/A"

        for tag in meta_tags:
            text = tag.text.strip()
            if 'Km' in text:
                kilometrage = text
            elif any(city in text for city in ['Cairo', 'Giza', 'Alexandria', 'Heliopolis']):
                location = text

        # Extract year from car name
        year = "N/A"
        year_match = re.search(r'\b20\d{2}\b', car_name)
        if year_match:
            year = year_match.group(0)

        # Extract listing URL
        listing_url = ""
        if car_header and 'href' in car_header.attrs:
            listing_url = f"https://eg.hatla2ee.com{car_header['href']}"

        # Extract listing date from otherData_Date
        date_elem = car.select_one('div.otherData_Date span')
        listing_time = date_elem.text.strip() if date_elem else "N/A"

        # Calculate days on website
        days_on_website = "N/A"
        if listing_time != "N/A":
            try:
                listing_date = datetime.strptime(listing_time.strip(), "%Y-%m-%d")
                current_date = datetime.now()
                days_on_website = (current_date - listing_date).days
            except Exception as e:
                print(f"Error parsing date {listing_time}: {str(e)}")
                pass

        # Create unique ID
        car_details = f"{dealer_code}_{car_name}_{year}_{kilometrage}"
        car_id = hashlib.md5(car_details.encode()).hexdigest()

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

def determine_website_type(url):
    """Determine which website scraper to use based on the URL."""
    if 'dubizzle.com' in url.lower():
        return 'dubizzle'
    elif 'hatla2ee.com' in url.lower():
        return 'hatla2ee'
    else:
        return 'unknown'

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
        # Update headers for dealers sheet to include Link 2
        dealer_headers = ['Code', 'Dealer', 'Link 1', 'Link 2']
        dealers_data = dealers_sheet.get_all_records(expected_headers=dealer_headers)

        # Get the database tab
        database_sheet = spreadsheet.worksheet('database')

        # Update headers for database sheet to include platform
        db_headers = ['car_id', 'dealer_code', 'created at', 'Car Brand', 'Car Name', 'Price', 
                     'Kilometrage', 'Year', 'Location', 'Listed', 'Days on Website', 'Listing URL', 
                     'status', 'platform']

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
            all_cars = []

            # Process Link 1
            if dealer['Link 1']:
                print(f"\nProcessing dealer: {dealer_name} (Code: {dealer_code}) - Link 1")
                website_type = determine_website_type(dealer['Link 1'])

                if website_type == 'dubizzle':
                    cars = scrape_dubizzle_cars(dealer['Link 1'], dealer_code)
                    for car in cars:
                        car['platform'] = 'dubizzle'
                    all_cars.extend(cars)
                elif website_type == 'hatla2ee':
                    cars = scrape_hatla2ee_cars(dealer['Link 1'], dealer_code)
                    for car in cars:
                        car['platform'] = 'hatla2ee'
                    all_cars.extend(cars)

            # Process Link 2 if it exists
            if dealer.get('Link 2'):
                print(f"\nProcessing dealer: {dealer_name} (Code: {dealer_code}) - Link 2")
                website_type = determine_website_type(dealer['Link 2'])

                if website_type == 'dubizzle':
                    cars = scrape_dubizzle_cars(dealer['Link 2'], dealer_code)
                    for car in cars:
                        car['platform'] = 'dubizzle'
                    all_cars.extend(cars)
                elif website_type == 'hatla2ee':
                    cars = scrape_hatla2ee_cars(dealer['Link 2'], dealer_code)
                    for car in cars:
                        car['platform'] = 'hatla2ee'
                    all_cars.extend(cars)

            # Deduplicate cars across platforms
            unique_cars = []
            seen_cars = set()

            for car in all_cars:
                # Create a key based on car details (excluding price and platform)
                car_key = f"{car['Car Name']}_{car['Year']}_{car['Kilometrage']}"

                if car_key not in seen_cars:
                    seen_cars.add(car_key)
                    unique_cars.append(car)
                else:
                    # If car exists on both platforms, update existing entry with both platforms
                    for existing_car in unique_cars:
                        existing_key = f"{existing_car['Car Name']}_{existing_car['Year']}_{existing_car['Kilometrage']}"
                        if existing_key == car_key:
                            existing_car['platform'] = f"{existing_car['platform']}, {car['platform']}"
                            break

            if not unique_cars:
                print(f"No car listings found for {dealer_name}.")
                continue

            print(f"Found {len(unique_cars)} unique car listings for {dealer_name}.")

            # Prepare data for Google Sheets
            rows_to_add = []
            dealer_new_cars = 0

            for car in unique_cars:
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
