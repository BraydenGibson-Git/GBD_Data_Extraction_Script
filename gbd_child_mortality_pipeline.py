#!/usr/bin/env python3
"""
GBD Child Mortality Data Processing Pipeline
============================================

This script extends the GBD data processing pipeline to include child mortality data,
a key component from the original master spreadsheet.

New Data Source:
- WHO Global Health Observatory (GHO)
- Indicator: Under-five mortality rate (per 1000 live births)
- API: GHO OData API (https://www.who.int/data/gho/info/gho-odata-api)

Pipeline Steps:
1. Run the original GBD data extraction for risk factors.
2. Extract Under-Five Mortality Rate data from the WHO GHO API.
3. Consolidate all data (risk factors + mortality).
4. Populate the master template with all data, including regional imputation.

Author: GBD Research Project
Date: July 2025
Version: 1.0 - Child Mortality Integration
"""

import pandas as pd
import requests
import os
from datetime import datetime
import warnings
from gbd_pipeline_final import run_complete_pipeline as run_risk_factor_pipeline
from gbd_enhanced_template_populator import EnhancedTemplatePopulator
warnings.filterwarnings('ignore')

# ===== CHILD MORTALITY EXTRACTION MODULE =====

class ChildMortalityExtractor:
    """
    Extracts child mortality data from the WHO Global Health Observatory (GHO)
    using the OData API.
    
    Indicator: Under-five mortality rate (per 1000 live births)
    SDG: 3.2.1
    GHO Code: MDG_0000000007
    """
    
    def __init__(self):
        self.base_url = "https://ghoapi.azureedge.net/api/MDG_0000000007"
        
    def extract_under_five_mortality(self):
        """
        Extracts under-five mortality rate for all countries and years.
        The API returns data in JSON format.
        """
        print("🌍 Extracting WHO Under-Five Mortality Rate data...")
        
        try:
            response = requests.get(self.base_url, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                records = self._parse_gho_data(data)
                print(f"   ✅ {len(records)} child mortality records extracted.")
                return pd.DataFrame(records)
            else:
                print(f"   ❌ HTTP Error {response.status_code}: Failed to fetch child mortality data.")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"   ❌ An error occurred: {e}")
            return pd.DataFrame()
            
    def _parse_gho_data(self, json_data):
        """
        Parses the JSON data from the GHO OData API.
        
        The structure is a root object with a 'value' key containing a list of records.
        Each record has properties like 'SpatialDim' (Country Code), 'TimeDim' (Year),
        and 'NumericValue'.
        """
        records = []
        
        if 'value' not in json_data:
            print("   ⚠️  'value' key not found in WHO API response.")
            return records
            
        country_code_map = self._get_country_code_map()
        
        for entry in json_data['value']:
            try:
                if entry['SpatialDimType'] == 'COUNTRY':
                    country_code = entry['SpatialDim']
                    country_name = country_code_map.get(country_code, country_code)
                    
                    record = {
                        'risk_factor': 'Child Mortality Rate (U5MR)',
                        'country': country_name,
                        'year': int(entry['TimeDim']),
                        'value': float(entry['NumericValue']),
                        'confidence_intervals': f"{entry.get('Low', 'N/A')}-{entry.get('High', 'N/A')}",
                        'sample_size': None,
                        'source': 'WHO_GHO'
                    }
                    records.append(record)
            except (KeyError, ValueError, TypeError) as e:
                # print(f"   ⚠️  Skipping record due to parsing error: {e}")
                continue
                
        return records
        
    def _get_country_code_map(self):
        """
        Fetches the mapping of country codes (e.g., 'USA') to country names 
        (e.g., 'United States of America') from the WHO API.
        """
        print("   🌐 Fetching country code to name mappings...")
        country_map = {}
        
        try:
            url = "https://ghoapi.azureedge.net/api/DIMENSION/COUNTRY/DimensionValues"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'value' in data:
                    for item in data['value']:
                        country_map[item['Code']] = item['Title']
                print(f"      ✅ Mapped {len(country_map)} country codes.")
            else:
                print(f"      ❌ Failed to fetch country codes (HTTP {response.status_code}).")
        
        except Exception as e:
            print(f"      ❌ Error fetching country codes: {e}")
            
        return country_map

# ===== MAIN PIPELINE INTEGRATION =====

def run_child_mortality_pipeline():
    """
    Runs the full pipeline:
    1. Extracts risk factor data.
    2. Extracts child mortality data.
    3. Consolidates data.
    4. Populates the final template.
    """
    
    print("🎯 === GBD CHILD MORTALITY PIPELINE ===")
    print(f"Started: {datetime.now()}")
    
    # --- Step 1: Run original risk factor pipeline ---
    # This will create 'gbd_processed_data/gbd_final_consolidated.xlsx'
    # We can optionally run it or assume it exists. For now, let's check.
    gbd_data_file = 'gbd_processed_data/gbd_final_consolidated.xlsx'
    if not os.path.exists(gbd_data_file):
        print("\nRisk factor data not found. Running the extraction pipeline first...")
        run_risk_factor_pipeline()
    else:
        print(f"\n✅ Risk factor data found: {gbd_data_file}")
        
    # --- Step 2: Extract Child Mortality Data ---
    print("\n MORTALITY DATA EXTRACTION ")
    mortality_extractor = ChildMortalityExtractor()
    mortality_df = mortality_extractor.extract_under_five_mortality()
    
    if mortality_df.empty:
        print("❌ Pipeline stopped: Child mortality data could not be extracted.")
        return
        
    # --- Step 3: Consolidate Data ---
    print("\n DATA CONSOLIDATION ")
    risk_factor_df = pd.read_excel(gbd_data_file, sheet_name='All_Data')
    
    # Combine the two dataframes
    consolidated_df = pd.concat([risk_factor_df, mortality_df], ignore_index=True)
    
    # Save the new consolidated file
    consolidated_output_file = 'gbd_processed_data/gbd_final_with_mortality.xlsx'
    with pd.ExcelWriter(consolidated_output_file, engine='openpyxl') as writer:
        consolidated_df.to_excel(writer, sheet_name='All_Data', index=False)
        risk_factor_df.to_excel(writer, sheet_name='Risk_Factors_Only', index=False)
        mortality_df.to_excel(writer, sheet_name='Child_Mortality_Only', index=False)
    
    print(f"   ✅ Consolidated data with mortality saved to: {consolidated_output_file}")
    
    # --- Step 4: Populate Template with Enhanced Data ---
    print("\n TEMPLATE POPULATION ")
    template_file = 'Master Spreadsheet (DO NOT CHANGE YET).xls'
    
    if not os.path.exists(template_file):
        print(f"❌ Master template file not found: {template_file}")
        return
        
    populator = EnhancedTemplatePopulator()
    
    # Run the enhanced populator with the new consolidated data
    populator.create_populated_template(template_file, consolidated_output_file)

    print("\n✅ Pipeline complete.")


if __name__ == "__main__":
    run_child_mortality_pipeline() 