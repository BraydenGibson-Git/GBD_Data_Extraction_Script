import pandas as pd
import os
import requests
import re
import time
import json
import numpy as np
from datetime import datetime
import argparse

# Configuration
CONFIG = {
    'output_dir': 'processed_data',
    'individual_sheets_dir': 'individual_sources',
    'summary_file': 'risk_factor_summary.xlsx',
    'all_data_file': 'all_extracted_data.xlsx'
}

# Global dictionary to store processed data for each risk factor
risk_factor_data = {}

def setup_output_directories():
    """Create output directories if they don't exist."""
    os.makedirs(CONFIG['output_dir'], exist_ok=True)
    individual_dir = os.path.join(CONFIG['output_dir'], CONFIG['individual_sheets_dir'])
    os.makedirs(individual_dir, exist_ok=True)
    print(f"Output directories created: {CONFIG['output_dir']}")

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

def save_summary_to_excel(combined_data):
    """Create a summary Excel file with pooled averages and statistics."""
    
    # Prepare headers and data
    headers = ["Risk Factor", "Number of Sources", "Metric", "Pooled Average", "Min", "Max", "Count", "Raw Values"]
    rows = []
    
    for risk_factor, data in combined_data.items():
        first_row = True
        for metric, stats in data['data'].items():
            row = {}
            if first_row:
                row['Risk Factor'] = risk_factor
                row['Number of Sources'] = data['sources']
                first_row = False
            else:
                row['Risk Factor'] = ''
                row['Number of Sources'] = ''
            
            row['Metric'] = metric
            
            if 'pooled_average' in stats:
                row['Pooled Average'] = round(stats['pooled_average'], 4)
                row['Min'] = round(stats['min'], 4)
                row['Max'] = round(stats['max'], 4)
                row['Count'] = stats['count']
                row['Raw Values'] = ', '.join(map(str, stats['raw_values'][:10]))  # Limit to first 10 values
            else:
                row['Pooled Average'] = 'N/A'
                row['Min'] = 'N/A'
                row['Max'] = 'N/A'
                row['Count'] = stats['count']
                row['Raw Values'] = ', '.join(map(str, stats['unique_values'][:10]))  # Limit to first 10 values
            
            rows.append(row)
    
    # Create DataFrame and save to Excel
    df = pd.DataFrame(rows)
    summary_path = os.path.join(CONFIG['output_dir'], CONFIG['summary_file'])
    
    try:
        df.to_excel(summary_path, index=False, engine='openpyxl')
        print(f"\nSummary saved to: {summary_path}")
        print(f"Summary contains {len(rows)} rows across {len(combined_data)} risk factors")
        return True
    except Exception as e:
        print(f"Error saving summary Excel file: {e}")
        return False

def save_all_data_to_excel():
    """Save all individual data sources to a single Excel file with multiple sheets."""
    all_data_path = os.path.join(CONFIG['output_dir'], CONFIG['all_data_file'])
    
    try:
        with pd.ExcelWriter(all_data_path, engine='openpyxl') as writer:
            sheet_count = 0
            
            for risk_factor, sources in risk_factor_data.items():
                for idx, source_data in enumerate(sources):
                    if isinstance(source_data, list) and len(source_data) > 0:
                        # Create sheet name
                        safe_risk_factor = re.sub(r'[^a-zA-Z0-9_.-]', '_', risk_factor)
                        sheet_name = f"{safe_risk_factor}_{idx+1}"[:31]  # Excel sheet names limited to 31 chars
                        
                        # Convert to DataFrame
                        if len(source_data) > 1:
                            df = pd.DataFrame(source_data[1:], columns=source_data[0])
                        else:
                            df = pd.DataFrame(source_data)
                        
                        # Save to sheet
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        sheet_count += 1
        
        print(f"\nAll data saved to: {all_data_path}")
        print(f"Created {sheet_count} sheets")
        return True
    except Exception as e:
        print(f"Error saving all data Excel file: {e}")
        return False

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
    """Process JSON data into a flat structure suitable for Excel."""
    if isinstance(data, dict):
        # If data is a dictionary, convert to a list of key-value pairs
        return [['Key', 'Value']] + [[k, str(v)] for k, v in data.items()]
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
            return [['Item']] + [[str(item)] for item in data]
    return [['Content'], [str(data)]]

def save_individual_data(risk_factor, data_source, data):
    """Save individual data source to local file."""
    # Sanitize names for file name
    safe_risk_factor = re.sub(r'[^a-zA-Z0-9_.-]', '_', risk_factor)
    safe_data_source = re.sub(r'[^a-zA-Z0-9_.-]', '_', data_source)
    
    # Create filename
    filename = f"{safe_risk_factor}_{safe_data_source}.xlsx"
    filepath = os.path.join(CONFIG['output_dir'], CONFIG['individual_sheets_dir'], filename)
    
    try:
        # Convert to DataFrame
        if isinstance(data, list) and len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
        else:
            df = pd.DataFrame(data)
        
        # Save to Excel
        df.to_excel(filepath, index=False, engine='openpyxl')
        print(f"Saved individual data to: {filepath}")
        return True
    except Exception as e:
        print(f"Error saving individual data: {e}")
        return False

def process_data_source(row):
    """Processes data from a URL and saves to local files."""
    risk_factor = row['Risk Factor']
    data_source = row['Data Source']
    url = row['API/Excel Download Link']

    # Initialize risk factor data storage if needed
    if risk_factor not in risk_factor_data:
        risk_factor_data[risk_factor] = []

    # Sanitize names for file name
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
            
            # Save individual data to local file
            save_individual_data(risk_factor, data_source, processed_data)
            
        except json.JSONDecodeError:
            print(f"\nWARNING: {data_source} response is not JSON")
            print(f"URL: {url}")
            print("First 200 characters of response:")
            print("-" * 50)
            print(response.text[:200] + "..." if len(response.text) > 200 else response.text)
            print("-" * 50)
            
            # Process as text anyway
            processed_data = [["Content"], [response.text]]
            risk_factor_data[risk_factor].append(processed_data)
            save_individual_data(risk_factor, data_source, processed_data)

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
    parser = argparse.ArgumentParser(description='Local Data Extractor - saves data to local files instead of Google Sheets')
    parser.add_argument('--output-dir', default='processed_data', help='Directory to save processed data')
    args = parser.parse_args()
    
    # Update config with command line args
    CONFIG['output_dir'] = args.output_dir
    
    print("=== Local Data Extractor ===")
    print(f"Output directory: {CONFIG['output_dir']}")
    
    # Setup output directories
    setup_output_directories()
    
    # Read and process data
    data_sources_df = read_data_sources(csv_file_path)
    
    if data_sources_df is not None:
        print("\nFirst 5 rows of the data:")
        print(data_sources_df.head())
        
        print(f"\n--- Starting Data Processing at {datetime.now()} ---")
        for index, row in data_sources_df.iterrows():
            process_data_source(row)
        
        print("\n--- Processing Pooled Averages ---")
        combined_data = combine_risk_factor_data()
        save_summary_to_excel(combined_data)
        
        print("\n--- Saving All Data to Excel ---")
        save_all_data_to_excel()
        
        print(f"\n--- Data Processing Finished at {datetime.now()} ---")
        print(f"\nAll files saved to: {CONFIG['output_dir']}")
        print("Files created:")
        print(f"  - {CONFIG['summary_file']} (Summary with pooled averages)")
        print(f"  - {CONFIG['all_data_file']} (All data in multiple sheets)")
        print(f"  - {CONFIG['individual_sheets_dir']}/ (Individual files for each data source)")
    else:
        print("Could not load data sources, skipping process.") 