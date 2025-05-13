import pandas as pd
import os
import requests
import re
import time
import json
import numpy as np
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
import pickle
import argparse

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Configuration
CONFIG = {
    'spreadsheet_id': None,  # Will be set from environment variable, command line arg, or user input
    'config_file': 'config.json'  # Local config file to store settings
}

# Global dictionary to store processed data for each risk factor
risk_factor_data = {}

def is_numeric(value):
    """Check if a value can be converted to a number."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def calculate_pooled_average(values):
    """Calculate pooled average from a list of numeric values."""
    numeric_values = [float(v) for v in values if is_numeric(v)]
    if numeric_values:
        return np.mean(numeric_values)
    return None

def combine_risk_factor_data():
    """Combine and process data from all sources for each risk factor."""
    combined_data = {}
    
    for risk_factor, sources in risk_factor_data.items():
        combined_data[risk_factor] = {
            'sources': len(sources),
            'data': {}
        }
        
        # Collect all unique keys across all sources
        all_keys = set()
        for source_data in sources:
            if isinstance(source_data, list) and len(source_data) > 1:
                # If data has headers (first row)
                headers = source_data[0]
                all_keys.update(headers)
        
        # Initialize combined data structure
        for key in all_keys:
            values = []
            for source_data in sources:
                if isinstance(source_data, list) and len(source_data) > 1:
                    headers = source_data[0]
                    if key in headers:
                        # Get column index
                        col_idx = headers.index(key)
                        # Add all values from this column (excluding header)
                        values.extend([row[col_idx] for row in source_data[1:]])
            
            # Calculate statistics for this key
            numeric_values = [v for v in values if is_numeric(v)]
            if numeric_values:
                numeric_values = [float(v) for v in numeric_values]
                combined_data[risk_factor]['data'][key] = {
                    'pooled_average': np.mean(numeric_values),
                    'min': min(numeric_values),
                    'max': max(numeric_values),
                    'count': len(numeric_values),
                    'raw_values': values
                }
            else:
                # For non-numeric data, store unique values
                combined_data[risk_factor]['data'][key] = {
                    'unique_values': list(set(values)),
                    'count': len(values),
                    'raw_values': values
                }
    
    return combined_data

def create_summary_sheet(service, spreadsheet_id, combined_data):
    """Create a summary sheet with pooled averages and statistics."""
    sheet_name = "Risk_Factor_Summary"
    
    # Prepare headers and data
    headers = ["Risk Factor", "Number of Sources", "Metric", "Pooled Average", "Min", "Max", "Count", "Raw Values"]
    rows = [headers]
    
    for risk_factor, data in combined_data.items():
        first_row = True
        for metric, stats in data['data'].items():
            row = []
            if first_row:
                row.extend([risk_factor, data['sources']])
                first_row = False
            else:
                row.extend(['', ''])  # Empty cells for risk factor and sources
            
            row.append(metric)
            
            if 'pooled_average' in stats:
                row.extend([
                    round(stats['pooled_average'], 4),
                    round(stats['min'], 4),
                    round(stats['max'], 4),
                    stats['count'],
                    ', '.join(map(str, stats['raw_values']))
                ])
            else:
                row.extend([
                    'N/A',  # No average for non-numeric
                    'N/A',  # No min
                    'N/A',  # No max
                    stats['count'],
                    ', '.join(map(str, stats['unique_values']))
                ])
            rows.append(row)
    
    # Upload to Google Sheets
    try:
        # Clear existing content
        range_name = f'{sheet_name}!A1:Z'
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()

        # Update with new data
        body = {
            'values': rows
        }
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        print(f"\nCreated summary sheet with {len(rows)} rows")
        return True
    except HttpError as error:
        print(f"Error updating summary sheet: {error}")
        return False

def load_config():
    """Load configuration from config file if it exists."""
    if os.path.exists(CONFIG['config_file']):
        try:
            with open(CONFIG['config_file'], 'r') as f:
                saved_config = json.load(f)
                CONFIG.update(saved_config)
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")

def save_config():
    """Save current configuration to config file."""
    try:
        with open(CONFIG['config_file'], 'w') as f:
            json.dump(CONFIG, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save config file: {e}")

def get_spreadsheet_id():
    """Get the spreadsheet ID from various sources."""
    # First try command line argument
    parser = argparse.ArgumentParser(description='Data Extractor with Google Sheets Integration')
    parser.add_argument('--spreadsheet-id', help='Google Sheets Spreadsheet ID')
    args = parser.parse_args()
    
    if args.spreadsheet_id:
        CONFIG['spreadsheet_id'] = args.spreadsheet_id
        save_config()
        return args.spreadsheet_id

    # Then try environment variable
    spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
    if spreadsheet_id:
        CONFIG['spreadsheet_id'] = spreadsheet_id
        save_config()
        return spreadsheet_id

    # Then try saved config
    if CONFIG.get('spreadsheet_id'):
        # Verify with user
        print(f"\nFound saved Spreadsheet ID: {CONFIG['spreadsheet_id']}")
        use_saved = input("Would you like to use this Spreadsheet ID? (y/n): ").lower().strip()
        if use_saved == 'y':
            return CONFIG['spreadsheet_id']

    # Finally, ask user
    while True:
        print("\nTo find your Spreadsheet ID:")
        print("1. Open your Google Sheet in a browser")
        print("2. Look at the URL: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit")
        print("3. Copy the SPREADSHEET_ID portion from the URL")
        spreadsheet_id = input("\nPlease enter the Google Spreadsheet ID: ").strip()
        
        # Basic validation
        if re.match(r'^[a-zA-Z0-9_-]+$', spreadsheet_id):
            CONFIG['spreadsheet_id'] = spreadsheet_id
            save_config()
            return spreadsheet_id
        else:
            print("Invalid Spreadsheet ID format. Please try again.")

def get_google_sheets_service():
    """Gets or creates Google Sheets credentials and returns the service."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        print(f"Error creating Google Sheets service: {e}")
        return None

# Define the path to the CSV file
csv_file_path = 'extracted_data_sources.csv'

def read_data_sources(file_path):
    """Reads the data sources CSV file into a pandas DataFrame."""
    try:
        df = pd.read_csv(file_path)
        print(f"Successfully read {len(df)} rows from {file_path}")
        # Basic check for expected columns
        expected_cols = ['Risk Factor', 'Assigned To', 'Data Source', 'API/Excel Download Link']
        if not all(col in df.columns for col in expected_cols):
            print(f"Warning: CSV file might be missing expected columns: {expected_cols}")
        return df
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None

def process_json_data(data):
    """Process JSON data into a flat structure suitable for Google Sheets."""
    if isinstance(data, dict):
        # If data is a dictionary, convert to a list of key-value pairs
        return [[k, str(v)] for k, v in data.items()]
    elif isinstance(data, list):
        # If data is a list of dictionaries, try to convert to a table structure
        if all(isinstance(item, dict) for item in data):
            # Get all unique keys
            keys = set()
            for item in data:
                keys.update(item.keys())
            keys = sorted(list(keys))
            
            # Create header row and data rows
            rows = [keys]  # Header row
            for item in data:
                row = [str(item.get(key, '')) for key in keys]
                rows.append(row)
            return rows
        else:
            # For simple lists, convert each item to string and create rows
            return [[str(item)] for item in data]
    return [[str(data)]]

def upload_to_sheets(service, spreadsheet_id, sheet_name, data):
    """Uploads data to a Google Sheet."""
    try:
        # Clear existing content
        range_name = f'{sheet_name}!A1:Z'
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()

        # Update with new data
        body = {
            'values': data
        }
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        print(f"Updated {result.get('updatedCells')} cells in {sheet_name}")
        return True
    except HttpError as error:
        print(f"Error updating Google Sheet: {error}")
        return False

def process_data_source(row, sheets_service=None, spreadsheet_id=None):
    """Processes data from a URL and uploads to Google Sheets."""
    risk_factor = row['Risk Factor']
    data_source = row['Data Source']
    url = row['API/Excel Download Link']

    # Initialize risk factor data storage if needed
    if risk_factor not in risk_factor_data:
        risk_factor_data[risk_factor] = []

    # Sanitize names for sheet name
    safe_risk_factor = re.sub(r'[^a-zA-Z0-9_.-]', '_', risk_factor)
    safe_data_source = re.sub(r'[^a-zA-Z0-9_.-]', '_', data_source)

    # Skip if URL is missing, invalid, or marked as N/A
    if pd.isna(url) or not isinstance(url, str) or url.strip() == '' or url.strip().upper() == 'N/A':
        print(f"Skipping {safe_risk_factor} - {safe_data_source}: No valid URL provided.")
        return

    # Add http:// if missing (simple check)
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
        print(f"Warning: Added 'http://' to URL for {safe_risk_factor} - {safe_data_source}")

    print(f"\nProcessing {safe_risk_factor} - {safe_data_source}: {url}")

    try:
        # Set a User-Agent header
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json'  # Prefer JSON response
        }
        response = requests.get(url, timeout=30, headers=headers, allow_redirects=True)
        response.raise_for_status()

        # Try to parse as JSON
        try:
            json_data = response.json()
            # Process JSON data
            processed_data = process_json_data(json_data)
            
            # Store processed data for pooled analysis
            risk_factor_data[risk_factor].append(processed_data)
            
            # Upload to Google Sheets if service is available
            if sheets_service and spreadsheet_id:
                sheet_name = f"{safe_risk_factor}_{safe_data_source}"[:31]  # Sheet names limited to 31 chars
                upload_to_sheets(sheets_service, spreadsheet_id, sheet_name, processed_data)
            else:
                print("Warning: Google Sheets service or spreadsheet ID not provided, skipping upload")
            
        except json.JSONDecodeError:
            print(f"\nERROR: {data_source} IS NOT JSON")
            print(f"URL: {url}")
            print("First 200 characters of response:")
            print("-" * 50)
            print(response.text[:200] + "..." if len(response.text) > 200 else response.text)
            print("-" * 50)
            
            while True:
                action = input("\nWhat would you like to do?\n"
                             "1. Skip this data source\n"
                             "2. Try to process as text anyway\n"
                             "3. View full response\n"
                             "4. Exit script\n"
                             "Enter choice (1-4): ").strip()
                
                if action == "1":
                    print(f"Skipping {data_source}")
                    return
                elif action == "2":
                    print(f"Processing {data_source} as text...")
                    processed_data = [["Content"], [response.text]]
                    if sheets_service and spreadsheet_id:
                        sheet_name = f"{safe_risk_factor}_{safe_data_source}"[:31]
                        upload_to_sheets(sheets_service, spreadsheet_id, sheet_name, processed_data)
                    return
                elif action == "3":
                    print("\nFull response:")
                    print("-" * 50)
                    print(response.text)
                    print("-" * 50)
                    continue
                elif action == "4":
                    print("Exiting script...")
                    exit(0)
                else:
                    print("Invalid choice. Please try again.")

    except requests.exceptions.Timeout:
        print(f"Error: Timeout occurred while trying to download {url}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred for {url}: {e}")

    # Add a small delay to avoid overwhelming servers
    time.sleep(1)

# Main execution
if __name__ == "__main__":
    # Load saved configuration
    load_config()
    
    # Initialize Google Sheets service
    sheets_service = get_google_sheets_service()
    
    if sheets_service:
        # Get spreadsheet ID
        spreadsheet_id = get_spreadsheet_id()
        
        if spreadsheet_id:
            try:
                # Verify spreadsheet access
                sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
                print(f"\nSuccessfully connected to spreadsheet: {spreadsheet_id}")
            except HttpError as error:
                if error.resp.status == 404:
                    print(f"Error: Could not find spreadsheet with ID: {spreadsheet_id}")
                    print("Please verify the Spreadsheet ID and make sure you have access to it.")
                    exit(1)
                else:
                    print(f"Error accessing spreadsheet: {error}")
                    exit(1)
            
            # Read and process data
            data_sources_df = read_data_sources(csv_file_path)
            
            if data_sources_df is not None:
                print("\nFirst 5 rows of the data:")
                print(data_sources_df.head())
                
                print("\n--- Starting Data Processing ---")
                for index, row in data_sources_df.iterrows():
                    process_data_source(row, sheets_service, spreadsheet_id)
                
                print("\n--- Processing Pooled Averages ---")
                combined_data = combine_risk_factor_data()
                create_summary_sheet(sheets_service, spreadsheet_id, combined_data)
                
                print("\n--- Data Processing Finished ---")
            else:
                print("Could not load data sources, skipping process.")
        else:
            print("No Spreadsheet ID provided. Exiting.")
    else:
        print("Could not initialize Google Sheets service. Exiting.") 