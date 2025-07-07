import pandas as pd
import os
import requests
import re
import time
import json
import numpy as np
from datetime import datetime
import argparse
from io import StringIO
import warnings
warnings.filterwarnings('ignore')

# Configuration for GBD analysis
CONFIG = {
    'output_dir': 'gbd_processed_data',
    'consolidated_file': 'gbd_consolidated_data.xlsx',
    'summary_file': 'gbd_summary_by_source.xlsx',
    'standardized_file': 'gbd_standardized_data.xlsx'
}

# Global storage for processed data
gbd_data_store = {}

def setup_output_directories():
    """Create output directories if they don't exist."""
    os.makedirs(CONFIG['output_dir'], exist_ok=True)
    print(f"GBD output directory created: {CONFIG['output_dir']}")

def standardize_country_names(country_name):
    """Standardize country names for GBD analysis."""
    if pd.isna(country_name):
        return country_name
    
    # Common country name mappings for GBD
    country_mapping = {
        'United States of America': 'United States',
        'Russian Federation': 'Russia',
        'Iran (Islamic Republic of)': 'Iran',
        'Republic of Korea': 'South Korea',
        "Democratic People's Republic of Korea": 'North Korea',
        'United Kingdom of Great Britain and Northern Ireland': 'United Kingdom',
        'Venezuela (Bolivarian Republic of)': 'Venezuela',
        'Bolivia (Plurinational State of)': 'Bolivia',
        'Tanzania (United Republic of)': 'Tanzania'
    }
    
    return country_mapping.get(str(country_name), str(country_name))

def process_unicef_data(json_data, risk_factor, data_source):
    """Process UNICEF SDMX JSON data for GBD analysis."""
    try:
        if 'data' not in json_data:
            return None
            
        data_sets = json_data['data'].get('dataSets', [])
        if not data_sets:
            return None
            
        # Extract observations and dimensional data
        structure = json_data.get('data', {}).get('structure', {})
        dimensions = structure.get('dimensions', {}).get('observation', [])
        
        # Find key dimensions
        country_dim = next((d for d in dimensions if d.get('id') in ['REF_AREA', 'COUNTRY']), None)
        time_dim = next((d for d in dimensions if d.get('id') in ['TIME_PERIOD', 'TIME']), None)
        
        rows = []
        for dataset in data_sets:
            observations = dataset.get('observations', {})
            
            for obs_key, obs_data in observations.items():
                if obs_data and len(obs_data) > 0:
                    value = obs_data[0] if obs_data[0] is not None else np.nan
                    
                    # Parse observation key to get dimensions
                    key_parts = obs_key.split(':')
                    
                    row = {
                        'risk_factor': risk_factor,
                        'data_source': data_source,
                        'value': value,
                        'country': 'Unknown',
                        'year': 'Unknown',
                        'age_group': 'Unknown',
                        'sex': 'Both',
                        'unit': 'Percentage',
                        'observation_key': obs_key
                    }
                    
                    # Map dimension values if structure is available
                    if country_dim and len(key_parts) > 0:
                        country_idx = next((i for i, d in enumerate(dimensions) if d.get('id') == country_dim.get('id')), None)
                        if country_idx is not None and len(key_parts) > country_idx:
                            country_values = country_dim.get('values', [])
                            if len(country_values) > int(key_parts[country_idx]):
                                row['country'] = country_values[int(key_parts[country_idx])].get('name', 'Unknown')
                    
                    if time_dim and len(key_parts) > 1:
                        time_idx = next((i for i, d in enumerate(dimensions) if d.get('id') == time_dim.get('id')), None)
                        if time_idx is not None and len(key_parts) > time_idx:
                            time_values = time_dim.get('values', [])
                            if len(time_values) > int(key_parts[time_idx]):
                                row['year'] = time_values[int(key_parts[time_idx])].get('name', 'Unknown')
                    
                    rows.append(row)
        
        return pd.DataFrame(rows) if rows else None
        
    except Exception as e:
        print(f"Error processing UNICEF data: {e}")
        return None

def process_dhs_data(json_data, risk_factor, data_source):
    """Process DHS API JSON data for GBD analysis."""
    try:
        if 'Data' not in json_data:
            return None
            
        data_list = json_data['Data']
        if not data_list:
            return None
            
        rows = []
        for item in data_list:
            row = {
                'risk_factor': risk_factor,
                'data_source': data_source,
                'country': standardize_country_names(item.get('CountryName', 'Unknown')),
                'country_code': item.get('DHS_CountryCode', ''),
                'year': item.get('SurveyYear', 'Unknown'),
                'survey_id': item.get('SurveyId', ''),
                'indicator': item.get('Indicator', ''),
                'characteristic_category': item.get('CharacteristicCategory', ''),
                'characteristic_label': item.get('CharacteristicLabel', ''),
                'value': pd.to_numeric(item.get('Value'), errors='coerce'),
                'confidence_interval_lower': pd.to_numeric(item.get('CILow'), errors='coerce'),
                'confidence_interval_upper': pd.to_numeric(item.get('CIHigh'), errors='coerce'),
                'sample_size': pd.to_numeric(item.get('SampleSize'), errors='coerce'),
                'age_group': item.get('CharacteristicLabel', 'Unknown'),
                'sex': 'Both',  # DHS often doesn't separate by sex for these indicators
                'unit': 'Percentage'
            }
            rows.append(row)
            
        return pd.DataFrame(rows) if rows else None
        
    except Exception as e:
        print(f"Error processing DHS data: {e}")
        return None

def process_who_csv_data(csv_text, risk_factor, data_source):
    """Process WHO CSV data for GBD analysis."""
    try:
        # Parse CSV from text
        df = pd.read_csv(StringIO(csv_text))
        
        # Standardize WHO column names
        column_mapping = {
            'GHO': 'indicator_code',
            'COUNTRY': 'country',
            'YEAR': 'year',
            'Display Value': 'display_value',
            'Numeric': 'value',
            'Low': 'confidence_interval_lower',
            'High': 'confidence_interval_upper',
            'REGION': 'who_region',
            'WORLDBANKINCOMEGROUP': 'income_group'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Add GBD-specific columns
        df['risk_factor'] = risk_factor
        df['data_source'] = data_source
        df['age_group'] = 'All ages'  # WHO data often aggregated
        df['sex'] = 'Both'
        
        # Determine unit based on indicator code
        if len(df) > 0 and 'indicator_code' in df.columns:
            first_indicator = df['indicator_code'].iloc[0] if pd.notna(df['indicator_code'].iloc[0]) else ''
            df['unit'] = 'Count' if 'NUM' in str(first_indicator) else 'Percentage'
        else:
            df['unit'] = 'Percentage'
        
        # Standardize country names
        if 'country' in df.columns:
            df['country'] = df['country'].apply(standardize_country_names)
        
        # Convert numeric columns
        numeric_cols = ['value', 'confidence_interval_lower', 'confidence_interval_upper', 'year']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df if len(df) > 0 else None
        
    except Exception as e:
        print(f"Error processing WHO CSV data: {e}")
        return None

def process_world_bank_data(json_data, risk_factor, data_source):
    """Process World Bank API JSON data for GBD analysis."""
    try:
        # World Bank data can have different structures
        if isinstance(json_data, list) and len(json_data) > 1:
            # Standard World Bank API format
            data_list = json_data[1] if len(json_data) > 1 else []
        elif isinstance(json_data, dict) and 'documents' in json_data:
            # World Bank search API format
            return None  # This is search results, not actual data
        else:
            return None
            
        if not data_list:
            return None
            
        rows = []
        for item in data_list:
            if isinstance(item, dict):
                row = {
                    'risk_factor': risk_factor,
                    'data_source': data_source,
                    'country': standardize_country_names(item.get('country', {}).get('value', 'Unknown')),
                    'country_code': item.get('countryiso3code', ''),
                    'year': pd.to_numeric(item.get('date'), errors='coerce'),
                    'value': pd.to_numeric(item.get('value'), errors='coerce'),
                    'indicator': item.get('indicator', {}).get('value', ''),
                    'indicator_id': item.get('indicator', {}).get('id', ''),
                    'age_group': 'All ages',
                    'sex': 'Both',
                    'unit': 'Percentage'
                }
                rows.append(row)
                
        return pd.DataFrame(rows) if rows else None
        
    except Exception as e:
        print(f"Error processing World Bank data: {e}")
        return None

def process_data_source_gbd(row):
    """Process a single data source with GBD-specific handling."""
    risk_factor = row['Risk Factor']
    data_source = row['Data Source']
    url = row['API/Excel Download Link']

    # Skip if URL is missing, invalid, or marked as N/A
    if pd.isna(url) or not isinstance(url, str) or url.strip() == '' or url.strip().upper() == 'N/A':
        print(f"⏭️  Skipping {risk_factor} - {data_source}: No valid URL provided.")
        return

    # Add http:// if missing
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    print(f"\n🔄 Processing {risk_factor} - {data_source}")
    print(f"   URL: {url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; GBD-DataExtractor/1.0)',
            'Accept': 'application/json, text/csv, text/plain'
        }
        response = requests.get(url, timeout=30, headers=headers, allow_redirects=True)
        response.raise_for_status()

        # Initialize processed data
        processed_df = None

        # Determine data source type and process accordingly
        if 'unicef' in url.lower() and 'sdmx' in url.lower():
            try:
                json_data = response.json()
                processed_df = process_unicef_data(json_data, risk_factor, data_source)
                print(f"   ✅ Processed UNICEF SDMX data")
            except json.JSONDecodeError:
                print(f"   ❌ Failed to parse UNICEF JSON")
                
        elif 'dhsprogram' in url.lower():
            try:
                json_data = response.json()
                processed_df = process_dhs_data(json_data, risk_factor, data_source)
                print(f"   ✅ Processed DHS data")
            except json.JSONDecodeError:
                print(f"   ❌ Failed to parse DHS JSON")
                
        elif 'who.int' in url.lower() or 'ghoapi' in url.lower():
            if 'format=csv' in url or response.headers.get('content-type', '').startswith('text/csv'):
                processed_df = process_who_csv_data(response.text, risk_factor, data_source)
                print(f"   ✅ Processed WHO CSV data")
            else:
                try:
                    json_data = response.json()
                    # WHO JSON data processing can be added here
                    print(f"   ⚠️  WHO JSON format not yet implemented")
                except:
                    print(f"   ❌ Unrecognized WHO data format")
                    
        elif 'worldbank' in url.lower():
            try:
                json_data = response.json()
                processed_df = process_world_bank_data(json_data, risk_factor, data_source)
                print(f"   ✅ Processed World Bank data")
            except json.JSONDecodeError:
                print(f"   ❌ Failed to parse World Bank JSON")
        else:
            print(f"   ⚠️  Unknown data source format")

        # Store processed data
        if processed_df is not None and len(processed_df) > 0:
            if risk_factor not in gbd_data_store:
                gbd_data_store[risk_factor] = {}
            gbd_data_store[risk_factor][data_source] = processed_df
            print(f"   📊 Extracted {len(processed_df)} records")
            
            # Save individual processed file
            safe_risk_factor = re.sub(r'[^a-zA-Z0-9_.-]', '_', risk_factor)
            safe_data_source = re.sub(r'[^a-zA-Z0-9_.-]', '_', data_source)
            filename = f"gbd_{safe_risk_factor}_{safe_data_source}.xlsx"
            filepath = os.path.join(CONFIG['output_dir'], filename)
            processed_df.to_excel(filepath, index=False, engine='openpyxl')
            print(f"   💾 Saved to: {filename}")
        else:
            print(f"   ⚠️  No usable data extracted")

    except requests.exceptions.Timeout:
        print(f"   ⏰ Timeout occurred")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {e}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")

    # Add delay to avoid overwhelming servers
    time.sleep(1)

def create_consolidated_dataset():
    """Create consolidated GBD dataset from all sources."""
    print(f"\n📋 Creating consolidated GBD dataset...")
    
    all_data = []
    source_summary = []
    
    for risk_factor, sources in gbd_data_store.items():
        for data_source, df in sources.items():
            if df is not None and len(df) > 0:
                all_data.append(df)
                
                # Create source summary
                summary = {
                    'risk_factor': risk_factor,
                    'data_source': data_source,
                    'records_count': len(df),
                    'countries_count': df['country'].nunique() if 'country' in df.columns else 0,
                    'years_range': f"{df['year'].min()}-{df['year'].max()}" if 'year' in df.columns and df['year'].notna().any() else 'Unknown',
                    'has_confidence_intervals': 'confidence_interval_lower' in df.columns and df['confidence_interval_lower'].notna().any(),
                    'avg_value': df['value'].mean() if 'value' in df.columns and df['value'].notna().any() else None
                }
                source_summary.append(summary)
    
    if all_data:
        # Combine all data
        consolidated_df = pd.concat(all_data, ignore_index=True, sort=False)
        
        # Standardize final dataset
        standard_columns = [
            'risk_factor', 'data_source', 'country', 'country_code', 'year', 
            'value', 'confidence_interval_lower', 'confidence_interval_upper',
            'age_group', 'sex', 'unit', 'sample_size'
        ]
        
        # Ensure all standard columns exist
        for col in standard_columns:
            if col not in consolidated_df.columns:
                consolidated_df[col] = np.nan
        
        # Save consolidated dataset
        consolidated_path = os.path.join(CONFIG['output_dir'], CONFIG['consolidated_file'])
        with pd.ExcelWriter(consolidated_path, engine='openpyxl') as writer:
            consolidated_df[standard_columns + [col for col in consolidated_df.columns if col not in standard_columns]].to_excel(
                writer, sheet_name='All_Data', index=False
            )
            
            # Create summary sheet
            pd.DataFrame(source_summary).to_excel(writer, sheet_name='Source_Summary', index=False)
            
            # Create data by risk factor sheets
            for risk_factor in consolidated_df['risk_factor'].unique():
                if pd.notna(risk_factor):
                    rf_data = consolidated_df[consolidated_df['risk_factor'] == risk_factor]
                    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', str(risk_factor))[:31]
                    rf_data.to_excel(writer, sheet_name=safe_name, index=False)
        
        print(f"✅ Consolidated dataset saved: {CONFIG['consolidated_file']}")
        print(f"   📊 Total records: {len(consolidated_df)}")
        print(f"   🌍 Countries: {consolidated_df['country'].nunique()}")
        print(f"   🗓️  Year range: {consolidated_df['year'].min()}-{consolidated_df['year'].max()}")
        
        return consolidated_df
    else:
        print("❌ No data to consolidate")
        return None

def read_data_sources(file_path):
    """Read the data sources CSV file."""
    try:
        df = pd.read_csv(file_path)
        print(f"📁 Successfully read {len(df)} data sources from {file_path}")
        return df
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='GBD Data Processor - Extract and standardize epidemiological data for GBD analysis')
    parser.add_argument('--output-dir', default='gbd_processed_data', help='Directory to save processed data')
    parser.add_argument('--csv-file', default='extracted_data_sources.csv', help='Input CSV file with data sources')
    args = parser.parse_args()
    
    # Update config
    CONFIG['output_dir'] = args.output_dir
    
    print("🌍 === GBD Data Processor ===")
    print(f"📂 Output directory: {CONFIG['output_dir']}")
    print(f"📄 Input file: {args.csv_file}")
    
    # Setup
    setup_output_directories()
    
    # Read data sources
    data_sources_df = read_data_sources(args.csv_file)
    if data_sources_df is None:
        return
    
    print(f"\n🔍 Processing {len(data_sources_df)} data sources...")
    
    # Process each data source
    for index, row in data_sources_df.iterrows():
        process_data_source_gbd(row)
    
    # Create consolidated dataset
    consolidated_data = create_consolidated_dataset()
    
    print(f"\n🎉 GBD data processing complete!")
    print(f"📁 All files saved to: {CONFIG['output_dir']}")

if __name__ == "__main__":
    main() 