import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import subprocess
import time

# Set page config
st.set_page_config(
    page_title="Dubizzle Car Listings Dashboard",
    page_icon="🚗",
    layout="wide"
)


# Function to load data from Google Sheets
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data():
    try:
        # Set up Google Sheets API
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        credentials = Credentials.from_service_account_file('sheet_access.json', scopes=scopes)
        gc = gspread.authorize(credentials)

        # Open the spreadsheet
        spreadsheet = gc.open('Dealers Dubizzle Scraper')

        # Get the database tab
        database_sheet = spreadsheet.worksheet('database')
        db_headers = ['car_id', 'dealer_code', 'created at', 'Car Brand', 'Car Name', 'Price',
                      'Kilometrage', 'Year', 'Location', 'Listed', 'Days on Website', 'Listing URL', 'status']
        data = database_sheet.get_all_records(expected_headers=db_headers)

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Get the dealers tab for dealer names
        dealers_sheet = spreadsheet.worksheet('dealers')
        dealer_headers = ['Code', 'Dealer', 'Link']
        dealers_data = dealers_sheet.get_all_records(expected_headers=dealer_headers)
        dealers_dict = {dealer['Code']: dealer['Dealer'] for dealer in dealers_data}

        # Add dealer name column
        df['Dealer Name'] = df['dealer_code'].map(dealers_dict)

        # Convert price to numeric
        df['Price'] = df['Price'].str.replace('EGP ', '').str.replace(',', '').astype(float)

        # Convert created_at to datetime
        df['created at'] = pd.to_datetime(df['created at'])

        # Convert Days on Website to numeric if possible
        df['Days on Website'] = pd.to_numeric(df['Days on Website'], errors='coerce')

        # Determine if listing is expired (not seen in last 3 days)
        latest_date = df['created at'].max()
        three_days_ago = latest_date - pd.Timedelta(days=3)

        # Group by car_id and get the most recent record for each car
        latest_records = df.sort_values('created at').groupby('car_id').last().reset_index()

        # Mark cars as expired if they haven't been seen in the last 3 days
        expired_car_ids = latest_records[latest_records['created at'] < three_days_ago]['car_id'].tolist()
        df['expired'] = df['car_id'].isin(expired_car_ids)

        # Sort by created_at
        df = df.sort_values('created at', ascending=False)

        return df, dealers_dict

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame(), {}


# Function to run the scraper
def run_scraper():
    try:
        result = subprocess.run(['python', 'dubizzle_scraper.py'],
                                capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


# Main app
def main():
    st.title("🚗 Dubizzle Car Listings Dashboard")


    # Load data
    with st.spinner("Loading data..."):
        df, dealers_dict = load_data()

    if df.empty:
        st.warning("No data available. Please run the scraper or check your Google Sheet.")
        return

    # Display last update time
    last_update = df['created at'].max()
    st.info(f"Last updated: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")

    # Overview metrics
    st.header("Overview")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        total_listings = len(df['car_id'].unique())
        st.metric("Total Unique Cars", total_listings)

    with col2:
        new_listings = len(df[df['status'] == 'new']['car_id'].unique())
        st.metric("New Cars", new_listings)

    with col3:
        expired_listings = len(df[df['expired']]['car_id'].unique())
        st.metric("Expired Listings", expired_listings)

    with col4:
        avg_price = df['Price'].mean()
        st.metric("Average Price", f"EGP {avg_price:,.0f}")

    with col5:
        dealers_count = df['dealer_code'].nunique()
        st.metric("Dealers", dealers_count)

    # Filters
    st.header("Filters")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        selected_dealers = st.multiselect(
            "Select Dealers",
            options=sorted(df['Dealer Name'].unique()),
            default=[]
        )

    with col2:
        selected_brands = st.multiselect(
            "Select Car Brands",
            options=sorted(df['Car Brand'].unique()),
            default=[]
        )

    with col3:
        price_range = st.slider(
            "Price Range (EGP)",
            min_value=int(df['Price'].min()),
            max_value=int(df['Price'].max()),
            value=(int(df['Price'].min()), int(df['Price'].max()))
        )

    with col4:
        listing_status = st.multiselect(
            "Listing Status",
            options=["New", "Existing", "Expired"],
            default=["New", "Existing"]
        )

    # Apply filters
    filtered_df = df.copy()

    if selected_dealers:
        filtered_df = filtered_df[filtered_df['Dealer Name'].isin(selected_dealers)]

    if selected_brands:
        filtered_df = filtered_df[filtered_df['Car Brand'].isin(selected_brands)]

    filtered_df = filtered_df[(filtered_df['Price'] >= price_range[0]) &
                              (filtered_df['Price'] <= price_range[1])]

    # Apply status filter
    status_conditions = []
    if "New" in listing_status:
        status_conditions.append(filtered_df['status'] == 'new')
    if "Existing" in listing_status:
        status_conditions.append(filtered_df['status'] == 'existing')
    if "Expired" in listing_status:
        status_conditions.append(filtered_df['expired'] == True)

    if status_conditions:
        filtered_df = filtered_df[pd.concat(status_conditions, axis=1).any(axis=1)]

    # Get unique cars after filtering
    unique_cars = filtered_df.sort_values('created at').groupby('car_id').last().reset_index()

    # Display filtered data count
    st.write(f"Showing {len(unique_cars)} unique car listings")

    # Visualizations
    st.header("Visualizations")

    tab1, tab2, tab3, tab4 = st.tabs(["Price Analysis", "Brand Distribution", "Listing Age", "Dealer Performance"])

    with tab1:
        # Price distribution by brand
        st.subheader("Price Distribution by Brand")
        fig = px.box(unique_cars, x='Car Brand', y='Price',
                     title='Price Distribution by Car Brand',
                     color='Car Brand')
        st.plotly_chart(fig, use_container_width=True)

        # Price vs. Year scatter plot
        st.subheader("Price vs. Year")
        fig = px.scatter(unique_cars, x='Year', y='Price',
                         color='Car Brand', size='Days on Website',
                         hover_data=['Car Name', 'Kilometrage', 'Dealer Name'],
                         title='Price vs. Year')
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # Brand distribution
        st.subheader("Car Brand Distribution")
        brand_counts = unique_cars['Car Brand'].value_counts()
        fig = px.pie(values=brand_counts.values, names=brand_counts.index,
                     title='Car Brand Distribution')
        st.plotly_chart(fig, use_container_width=True)

        # Brand distribution by dealer
        st.subheader("Brand Distribution by Dealer")
        dealer_brand_counts = unique_cars.groupby(['Dealer Name', 'Car Brand']).size().reset_index(name='Count')
        fig = px.bar(dealer_brand_counts, x='Dealer Name', y='Count', color='Car Brand',
                     title='Brand Distribution by Dealer')
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        # Listing age distribution
        st.subheader("Listing Age Distribution")
        fig = px.histogram(unique_cars, x='Days on Website',
                           title='Listing Age Distribution (Days)',
                           nbins=20)
        st.plotly_chart(fig, use_container_width=True)

        # Average listing age by dealer
        st.subheader("Average Listing Age by Dealer")
        avg_age_by_dealer = unique_cars.groupby('Dealer Name')['Days on Website'].mean().reset_index()
        fig = px.bar(avg_age_by_dealer, x='Dealer Name', y='Days on Website',
                     title='Average Listing Age by Dealer (Days)')
        st.plotly_chart(fig, use_container_width=True)

    with tab4:
        # Dealer performance metrics
        st.subheader("Dealer Performance")

        # Calculate metrics per dealer
        dealer_metrics = unique_cars.groupby('Dealer Name').agg({
            'car_id': 'count',
            'Price': 'mean',
            'Days on Website': 'mean',
            'expired': lambda x: (x == True).sum(),
            'status': lambda x: (x == 'new').sum()
        }).reset_index()

        dealer_metrics.columns = ['Dealer Name', 'Total Cars', 'Avg Price', 'Avg Days Listed', 'Expired Cars',
                                  'New Cars']

        # Calculate turnover rate (expired / total)
        dealer_metrics['Turnover Rate'] = dealer_metrics['Expired Cars'] / dealer_metrics['Total Cars']

        # Display metrics table
        st.dataframe(
            dealer_metrics,
            column_config={
                "Dealer Name": st.column_config.TextColumn("Dealer"),
                "Total Cars": st.column_config.NumberColumn("Total Cars"),
                "Avg Price": st.column_config.NumberColumn("Avg Price (EGP)", format="EGP %,.0f"),
                "Avg Days Listed": st.column_config.NumberColumn("Avg Days Listed", format="%.1f days"),
                "Expired Cars": st.column_config.NumberColumn("Expired Cars"),
                "New Cars": st.column_config.NumberColumn("New Cars"),
                "Turnover Rate": st.column_config.ProgressColumn("Turnover Rate", format="%.2f", min_value=0,
                                                                 max_value=1)
            },
            use_container_width=True,
            hide_index=True
        )

        # Dealer comparison chart
        st.subheader("Dealer Comparison")
        metric_options = ["Total Cars", "Avg Price", "Avg Days Listed", "Expired Cars", "New Cars", "Turnover Rate"]
        selected_metric = st.selectbox("Select Metric", metric_options)

        fig = px.bar(dealer_metrics, x='Dealer Name', y=selected_metric,
                     title=f'{selected_metric} by Dealer',
                     color='Dealer Name')
        st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.header("Car Listings")

    # Select columns to display
    display_cols = ['Car Brand', 'Car Name', 'Price', 'Year', 'Kilometrage',
                    'Location', 'Listed', 'Days on Website', 'Dealer Name', 'status']

    # Add status indicators
    unique_cars_display = unique_cars[display_cols].copy()
    unique_cars_display['Status'] = unique_cars.apply(
        lambda x: "🆕 New" if x['status'] == 'new' else ("⚠️ Expired" if x['expired'] else "✅ Active"),
        axis=1
    )

    # Add URL column with clickable links
    unique_cars_display['View'] = unique_cars['Listing URL'].apply(
        lambda x: f'<a href="{x}" target="_blank">View Listing</a>' if x != "N/A" else "N/A"
    )

    # Display the data table
    st.dataframe(
        unique_cars_display,
        column_config={
            "Car Name": st.column_config.TextColumn("Car Name"),
            "Price": st.column_config.NumberColumn("Price (EGP)", format="EGP %,.0f"),
            "Days on Website": st.column_config.NumberColumn("Days on Website", format="%.2f days"),
            "Status": st.column_config.TextColumn("Status"),
            "View": st.column_config.LinkColumn("View Listing")
        },
        use_container_width=True,
        hide_index=True
    )

    # Add a section with featured listings
    st.header("Featured Listings")

    # Display 5 newest and 5 most expensive listings
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Newest Listings")
        newest = unique_cars[unique_cars['status'] == 'new'].sort_values('created at', ascending=False).head(5)
        for _, row in newest.iterrows():
            with st.container():
                st.markdown(f"**{row['Car Brand']} {row['Car Name']}** - {row['Year']}")
                st.markdown(f"💰 **Price:** EGP {row['Price']:,.0f} | 🚗 **Kilometrage:** {row['Kilometrage']}")
                st.markdown(f"📍 **Location:** {row['Location']} | 🏢 **Dealer:** {row['Dealer Name']}")
                st.markdown(f"[View Listing]({row['Listing URL']})")
                st.divider()

    with col2:
        st.subheader("Premium Listings")
        premium = unique_cars.sort_values('Price', ascending=False).head(5)
        for _, row in premium.iterrows():
            with st.container():
                st.markdown(f"**{row['Car Brand']} {row['Car Name']}** - {row['Year']}")
                st.markdown(f"💰 **Price:** EGP {row['Price']:,.0f} | 🚗 **Kilometrage:** {row['Kilometrage']}")
                st.markdown(f"📍 **Location:** {row['Location']} | 🏢 **Dealer:** {row['Dealer Name']}")
                st.markdown(f"[View Listing]({row['Listing URL']})")
                st.divider()


if __name__ == "__main__":
    main()
