#!/usr/bin/env python3
"""
GBD Data Processing Pipeline - Final Consolidated Version
========================================================

This script provides a complete, one-stop pipeline for extracting epidemiological data,
including risk factors and child mortality, and populating a master research template.

Pipeline Steps:
1. Extracts risk factor data (Malnutrition, Crowding, etc.) from UNICEF, DHS, WHO, and World Bank.
2. Extracts Under-Five Mortality Rate data from the WHO Global Health Observatory.
3. Consolidates all data into a single file.
4. Uses the consolidated data to populate the master research template, applying
   a data-driven, sub-regional stratification based on child mortality rates.

To Run:
- Ensure all dependencies are installed (`pip install -r requirements.txt`)
- Execute the script from your terminal: `python gbd_pipeline_final.py`
"""

import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime
import warnings
import os
from urllib.parse import quote
from gbd_enhanced_template_populator import EnhancedTemplatePopulator
warnings.filterwarnings('ignore')

# ===== DATA EXTRACTION MODULES =====

class UNICEFMICSExtractor:
    """Extract data from UNICEF Statistical Data Warehouse (SDMX API)"""
    
    def __init__(self):
        self.base_url = "https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data"
        
    def extract_malnutrition_data(self):
        """Extract malnutrition data (weight-for-age z<-2)"""
        print("   📊 Extracting UNICEF malnutrition data...")
        
        # UNICEF malnutrition indicator
        indicator = "NUTRITION_022"  # Weight for age below -2 SD
        
        try:
            url = f"{self.base_url}/UNICEF,{indicator}/all/all"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                records = self._parse_sdmx_data(data, "Malnutrition (wght-for-age z<-2)")
                print(f"      ✅ {len(records)} malnutrition records extracted")
                return records
            else:
                print(f"      ❌ HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"      ❌ Error: {e}")
            return []
    
    def extract_crowding_data(self):
        """Extract household crowding data"""
        print("   🏠 Extracting UNICEF crowding data...")
        
        # UNICEF household overcrowding indicator
        indicator = "PT_CHLD_5-PCAP"  # Children living in crowded households
        
        try:
            url = f"{self.base_url}/UNICEF,{indicator}/all/all"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                records = self._parse_sdmx_data(data, "Crowding (5 or more persons)")
                print(f"      ✅ {len(records)} crowding records extracted")
                return records
            else:
                print(f"      ❌ HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"      ❌ Error: {e}")
            return []
    
    def _parse_sdmx_data(self, json_data, risk_factor):
        """Parse SDMX JSON format"""
        records = []
        
        try:
            if 'data' in json_data and 'dataSets' in json_data['data']:
                datasets = json_data['data']['dataSets']
                structure = json_data['data']['structure']
                
                # Extract observations
                for dataset in datasets:
                    if 'observations' in dataset:
                        for obs_key, obs_data in dataset['observations'].items():
                            try:
                                # Parse observation key
                                indices = [int(x) for x in obs_key.split(':')]
                                
                                # Extract country and time
                                country_idx = indices[1] if len(indices) > 1 else 0
                                time_idx = indices[-1] if len(indices) > 0 else 0
                                
                                # Get country name
                                countries = structure['dimensions']['observation'][1]['values']
                                country = countries[country_idx]['name'] if country_idx < len(countries) else 'Unknown'
                                
                                # Get time period
                                times = structure['dimensions']['observation'][-1]['values']
                                time_period = times[time_idx]['id'] if time_idx < len(times) else 'Unknown'
                                
                                # Extract value
                                value = obs_data[0] if isinstance(obs_data, list) and len(obs_data) > 0 else obs_data
                                
                                if isinstance(value, (int, float)) and not np.isnan(value):
                                    records.append({
                                        'risk_factor': risk_factor,
                                        'country': country,
                                        'year': int(time_period) if str(time_period).isdigit() else np.nan,
                                        'value': float(value),
                                        'confidence_intervals': None,
                                        'sample_size': None,
                                        'source': 'UNICEF_MICS'
                                    })
                                    
                            except (IndexError, ValueError, TypeError):
                                continue
                                
        except Exception as e:
            print(f"      ⚠️ SDMX parsing error: {e}")
            
        return records

class DHSExtractor:
    """Extract data from DHS Program API"""
    
    def __init__(self):
        self.base_url = "https://api.dhsprogram.com/rest/dhs/data"
        
    def extract_all_indicators(self):
        """Extract all DHS indicators for the 5 risk factors"""
        print("   📊 Extracting DHS data...")
        
        indicators = {
            'CN_NUTS_C_HA2': 'Malnutrition (wght-for-age z<-2)',
            'RH_DELA_C_LBW': 'Low birth weight (=<2500 g)',
            'FE_BRFS_C_EXB': 'Non-breastfed exclus. (4 mths)',
            'HC_HFOK_H_CKF': 'Use solid fuels (yes)',
            'HC_HFOK_H_NPP': 'Crowding (5 or more persons)'
        }
        
        all_records = []
        
        for indicator_id, risk_factor in indicators.items():
            print(f"      📋 Processing {risk_factor}...")
            records = self._extract_indicator(indicator_id, risk_factor)
            all_records.extend(records)
            time.sleep(1)  # Rate limiting
            
        print(f"   ✅ Total DHS records: {len(all_records)}")
        return all_records
    
    def _extract_indicator(self, indicator_id, risk_factor):
        """Extract specific DHS indicator"""
        records = []
        
        try:
            url = f"{self.base_url}?indicatorIds={indicator_id}&f=json&perPage=5000"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'Data' in data:
                    for record in data['Data']:
                        try:
                            country = record.get('CountryName', 'Unknown')
                            year = record.get('SurveyYear')
                            value = record.get('Value')
                            ci_lower = record.get('CI_Lower')
                            ci_upper = record.get('CI_Upper')
                            sample_size = record.get('TotalUnweighted')
                            
                            if value is not None and country != 'Unknown':
                                confidence_interval = None
                                if ci_lower is not None and ci_upper is not None:
                                    confidence_interval = f"{ci_lower}-{ci_upper}"
                                
                                records.append({
                                    'risk_factor': risk_factor,
                                    'country': country,
                                    'year': int(year) if year else np.nan,
                                    'value': float(value),
                                    'confidence_intervals': confidence_interval,
                                    'sample_size': int(sample_size) if sample_size else None,
                                    'source': 'DHS'
                                })
                                
                        except (ValueError, TypeError):
                            continue
                            
        except Exception as e:
            print(f"      ❌ Error extracting {indicator_id}: {e}")
            
        return records

class WHOExtractor:
    """Extract data from WHO Global Health Observatory"""
    
    def __init__(self):
        self.base_url = "https://ghoapi.azureedge.net/api"
        
    def extract_indicators(self):
        """Extract WHO health indicators"""
        print("   🏥 Extracting WHO data...")
        
        indicators = {
            'NUTRITION_ANAEMIA_CHILDREN_PREV': 'Malnutrition (wght-for-age z<-2)',
            'REPRO_LOWBIRTHWEIGHT': 'Low birth weight (=<2500 g)',
            'NUT_STUNTING': 'Malnutrition (wght-for-age z<-2)'
        }
        
        all_records = []
        
        for indicator_code, risk_factor in indicators.items():
            print(f"      📋 Processing {risk_factor}...")
            records = self._extract_indicator(indicator_code, risk_factor)
            all_records.extend(records)
            time.sleep(1)
            
        print(f"   ✅ Total WHO records: {len(all_records)}")
        return all_records
    
    def _extract_indicator(self, indicator_code, risk_factor):
        """Extract specific WHO indicator"""
        records = []
        
        try:
            url = f"{self.base_url}/{indicator_code}"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'value' in data:
                    for record in data['value']:
                        try:
                            country = record.get('SpatialDim', 'Unknown')
                            year = record.get('TimeDim')
                            value = record.get('NumericValue')
                            
                            if value is not None and country != 'Unknown':
                                records.append({
                                    'risk_factor': risk_factor,
                                    'country': country,
                                    'year': int(year) if year else np.nan,
                                    'value': float(value),
                                    'confidence_intervals': None,
                                    'sample_size': None,
                                    'source': 'WHO'
                                })
                                
                        except (ValueError, TypeError):
                            continue
                            
        except Exception as e:
            print(f"      ❌ Error extracting {indicator_code}: {e}")
            
        return records

class WorldBankExtractor:
    """Extract data from World Bank API"""
    
    def __init__(self):
        self.base_url = "https://api.worldbank.org/v2"
        
    def extract_indicators(self):
        """Extract World Bank health indicators"""
        print("   🌍 Extracting World Bank data...")
        
        indicators = {
            'SH.STA.MALN.ZS': 'Malnutrition (wght-for-age z<-2)',
            'SH.STA.BRTW.ZS': 'Low birth weight (=<2500 g)'
        }
        
        all_records = []
        
        for indicator_code, risk_factor in indicators.items():
            print(f"      📋 Processing {risk_factor}...")
            records = self._extract_indicator(indicator_code, risk_factor)
            all_records.extend(records)
            time.sleep(1)
            
        print(f"   ✅ Total World Bank records: {len(all_records)}")
        return all_records
    
    def _extract_indicator(self, indicator_code, risk_factor):
        """Extract specific World Bank indicator"""
        records = []
        
        try:
            url = f"{self.base_url}/countries/all/indicators/{indicator_code}?format=json&date=1990:2025&per_page=20000"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if len(data) > 1 and data[1]:
                    for record in data[1]:
                        try:
                            country = record.get('country', {}).get('value', 'Unknown')
                            year = record.get('date')
                            value = record.get('value')
                            
                            if value is not None and country != 'Unknown':
                                records.append({
                                    'risk_factor': risk_factor,
                                    'country': country,
                                    'year': int(year) if year else np.nan,
                                    'value': float(value),
                                    'confidence_intervals': None,
                                    'sample_size': None,
                                    'source': 'World_Bank'
                                })
                                
                        except (ValueError, TypeError):
                            continue
                            
        except Exception as e:
            print(f"      ❌ Error extracting {indicator_code}: {e}")
            
        return records

# ===== NEW: CHILD MORTALITY EXTRACTOR =====
class ChildMortalityExtractor:
    """
    Extracts child mortality data from the WHO Global Health Observatory (GHO).
    Indicator: Under-five mortality rate (per 1000 live births) [MDG_0000000007]
    """
    def __init__(self):
        self.base_url = "https://ghoapi.azureedge.net/api/MDG_0000000007"
        
    def extract_under_five_mortality(self):
        print(" MORTALITY DATA EXTRACTION ")
        print("   🌍 Extracting WHO Under-Five Mortality Rate data...")
        try:
            response = requests.get(self.base_url, timeout=60)
            if response.status_code == 200:
                records = self._parse_gho_data(response.json())
                print(f"      ✅ {len(records)} child mortality records extracted.")
                return pd.DataFrame(records)
            else:
                print(f"      ❌ HTTP Error {response.status_code}")
                return pd.DataFrame()
        except Exception as e:
            print(f"      ❌ An error occurred: {e}")
            return pd.DataFrame()
            
    def _parse_gho_data(self, json_data):
        records = []
        if 'value' not in json_data: return records
        country_map = self._get_country_code_map()
        for entry in json_data['value']:
            if entry.get('SpatialDimType') == 'COUNTRY':
                country_code = entry['SpatialDim']
                records.append({
                    'risk_factor': 'Child Mortality Rate (U5MR)',
                    'country': country_map.get(country_code, country_code),
                    'year': int(entry['TimeDim']),
                    'value': float(entry['NumericValue']),
                    'confidence_intervals': f"{entry.get('Low', 'N/A')}-{entry.get('High', 'N/A')}",
                    'sample_size': None, 'source': 'WHO_GHO'
                })
        return records
        
    def _get_country_code_map(self):
        print("      🌐 Fetching country code to name mappings...")
        country_map = {}
        try:
            url = "https://ghoapi.azureedge.net/api/DIMENSION/COUNTRY/DimensionValues"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                for item in response.json().get('value', []):
                    country_map[item['Code']] = item['Title']
            print(f"         ✅ Mapped {len(country_map)} country codes.")
        except Exception as e:
            print(f"         ❌ Error fetching country codes: {e}")
        return country_map

# ===== MAIN PIPELINE =====

def run_complete_pipeline():
    """
    Complete GBD Data Processing and Template Population Pipeline
    """
    print("🎯 === GBD DATA PROCESSING & POPULATION PIPELINE ===")
    print(f"Started: {datetime.now()}")
    
    # === STAGE 1: EXTRACT RISK FACTOR DATA ===
    print("\n📊 === STAGE 1: RISK FACTOR DATA EXTRACTION ===")
    all_records = []
    
    # UNICEF MICS
    print("🦄 UNICEF MICS Extraction:")
    unicef = UNICEFMICSExtractor()
    all_records.extend(unicef.extract_malnutrition_data())
    all_records.extend(unicef.extract_crowding_data())
    
    # DHS
    print("\n📋 DHS Program Extraction:")
    dhs = DHSExtractor()
    all_records.extend(dhs.extract_all_indicators())
    
    # WHO
    print("\n🏥 WHO Global Health Observatory:")
    who = WHOExtractor()
    all_records.extend(who.extract_indicators())
    
    # World Bank
    print("\n🌍 World Bank Extraction:")
    wb = WorldBankExtractor()
    all_records.extend(wb.extract_indicators())
    
    risk_factor_df = pd.DataFrame(all_records)
    print(f"\n   ✅ Total risk factor records extracted: {len(risk_factor_df)}")

    # === STAGE 2: EXTRACT CHILD MORTALITY DATA ===
    mortality_extractor = ChildMortalityExtractor()
    mortality_df = mortality_extractor.extract_under_five_mortality()
    
    if mortality_df.empty:
        print("❌ Pipeline stopped: Child mortality data could not be extracted.")
        return

    # === STAGE 3: CONSOLIDATE ALL DATA ===
    print("\n💾 === STAGE 3: DATA CONSOLIDATION ===")
    consolidated_df = pd.concat([risk_factor_df, mortality_df], ignore_index=True)
    
    output_dir = 'gbd_processed_data'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    consolidated_output_file = os.path.join(output_dir, 'gbd_final_with_mortality.xlsx')
    consolidated_df.to_excel(consolidated_output_file, sheet_name='All_Data', index=False)
    print(f"   ✅ All data consolidated into: {consolidated_output_file}")
    
    # === STAGE 4: POPULATE TEMPLATE WITH SUB-REGIONAL STRATIFICATION ===
    print("\n🔧 === STAGE 4: TEMPLATE POPULATION ===")
    template_file = 'Master Spreadsheet (DO NOT CHANGE YET).xls'
    if not os.path.exists(template_file):
        print(f"   ❌ Master template file not found: {template_file}")
        return
        
    populator = EnhancedTemplatePopulator()
    final_template_path = populator.create_populated_template(template_file, consolidated_output_file)
    
    if final_template_path:
        print(f"\n📊 === FINAL RESULTS ===")
        print(f"   ✅ Final stratified template created: {final_template_path}")
    else:
        print("   ❌ Failed to create the final template.")

    print(f"\n🎉 Pipeline completed: {datetime.now()}")

if __name__ == "__main__":
    run_complete_pipeline() 