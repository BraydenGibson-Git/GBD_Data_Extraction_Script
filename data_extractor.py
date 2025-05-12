import pandas as pd
import os
import requests
import re
import time

# Define the path to the CSV file
csv_file_path = 'extracted_data_sources.csv'

# Define the directory to save downloaded files
download_dir = 'downloaded_data'

# Create the download directory if it doesn't exist
os.makedirs(download_dir, exist_ok=True)

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

# Read the data
data_sources_df = read_data_sources(csv_file_path)

# Display the first few rows if the DataFrame was loaded successfully
if data_sources_df is not None:
    print("\nFirst 5 rows of the data:")
    print(data_sources_df.head())

# --- Helper function to sanitize filenames ---
def sanitize_filename(name):
    """Removes invalid characters for filenames."""
    # Remove parentheses and content within them
    name = re.sub(r'\(.*?\)', '', name).strip()
    # Replace spaces and invalid characters with underscores
    name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    # Remove consecutive underscores
    name = re.sub(r'_+', '_', name)
    # Remove leading/trailing underscores
    name = name.strip('_')
    return name

# --- Function to download and save data ---
def download_and_save_data(row, save_dir):
    """Downloads data from a URL specified in the row and saves it."""
    risk_factor = row['Risk Factor']
    data_source = row['Data Source']
    url = row['API/Excel Download Link']

    # Sanitize names for filename
    safe_risk_factor = sanitize_filename(risk_factor)
    safe_data_source = sanitize_filename(data_source)

    # Skip if URL is missing, invalid, or marked as N/A
    if pd.isna(url) or not isinstance(url, str) or url.strip() == '' or url.strip().upper() == 'N/A':
        print(f"Skipping {safe_risk_factor} - {safe_data_source}: No valid URL provided.")
        return

    # Add http:// if missing (simple check)
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
        print(f"Warning: Added 'http://' to URL for {safe_risk_factor} - {safe_data_source}")

    print(f"Processing {safe_risk_factor} - {safe_data_source}: {url}")

    try:
        # Set a User-Agent header
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=30, headers=headers, allow_redirects=True)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        # Determine file extension
        content_type = response.headers.get('content-type')
        extension = '.data' # Default extension
        if content_type:
            if 'json' in content_type:
                extension = '.json'
            elif 'csv' in content_type:
                extension = '.csv'
            elif 'excel' in content_type or 'spreadsheetml' in content_type:
                extension = '.xlsx'
            elif 'xml' in content_type:
                extension = '.xml'
            elif 'html' in content_type:
                print(f"Warning: URL points to an HTML page, saving as .html: {url}")
                extension = '.html'
        else:
            # Try guessing from URL
            if url.lower().endswith('.csv'):
                extension = '.csv'
            elif url.lower().endswith('.json'):
                extension = '.json'
            elif url.lower().endswith('.xlsx'):
                extension = '.xlsx'
            elif url.lower().endswith('.xml'):
                extension = '.xml'

        # Construct filename and save path
        filename = f"{safe_risk_factor}_{safe_data_source}{extension}"
        save_path = os.path.join(save_dir, filename)

        # Save the content
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"Successfully downloaded and saved to {save_path}")

    except requests.exceptions.Timeout:
        print(f"Error: Timeout occurred while trying to download {url}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
    except IOError as e:
        print(f"Error saving file {save_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred for {url}: {e}")

    # Add a small delay to avoid overwhelming servers
    time.sleep(1)

# Display the first few rows if the DataFrame was loaded successfully
if data_sources_df is not None:
    print("\nFirst 5 rows of the data:")
    print(data_sources_df.head())

    # --- Iterate through the DataFrame and download data ---
    print(f"\n--- Starting Data Download --- (Saving to '{download_dir}')")
    for index, row in data_sources_df.iterrows():
        download_and_save_data(row, download_dir)

    print("\n--- Data Download Process Finished ---")
else:
    print("Could not load data sources, skipping download process.")

# --- Next steps will involve iterating through this DataFrame --- 