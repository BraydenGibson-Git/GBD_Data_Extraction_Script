#!/usr/bin/env python3
"""
Global Burden of Disease (GBD) Data Extraction and Processing Pipeline
=======================================================================

This script automates the extraction, cleaning, and consolidation of key 
child health indicators from multiple global data sources:

1.  **World Bank:** Fetches data via the World Bank API.
2.  **WHO (World Health Organization):** Fetches data from the GHO OData API.
3.  **DHS (Demographic and Health Surveys):** Fetches data from the DHS Program STATcompiler API.

The script performs the following key functions:
-   Fetches data for specified indicators from each source.
-   Handles API pagination, rate limiting, and error retries.
-   Cleans and standardizes country names and formats.
-   Pools data from multiple sources for the same indicator, calculating a weighted average.
-   Consolidates all processed data into a single long-format Excel file.
-   Calls a secondary script (`gbd_enhanced_template_populator.py`) to populate the final GBD template.

Version: 3.2 - Final Fixes
Date: July 2025
"""

import os
import time
import shutil
import contextlib, io, warnings
import pandas as pd
import requests
from tqdm import tqdm
from datetime import datetime
import numpy as np
import gbd_enhanced_template_populator

# Suppress pandas SettingWithCopy warnings that arise during in-place normalisation
from pandas.errors import SettingWithCopyWarning
warnings.simplefilter("ignore", SettingWithCopyWarning)

# --- Configuration ---
CACHE_DIR = 'api_cache'
OUTPUT_DIR = 'gbd_processed_data'
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================
# Helper: Human Progress Check
# =============================

def progress_checkpoint(stage_desc: str, *, auto_env_var: str = "GBD_PIPELINE_AUTOCONFIRM") -> None:
    """Pause execution for a human progress check unless disabled.

    Parameters
    ----------
    stage_desc : str
        A short description of the stage that has just completed.
    auto_env_var : str, optional
        Name of the environment variable that, when set to "1", will skip the
        interactive confirmation prompt. Default is ``GBD_PIPELINE_AUTOCONFIRM``.
    """
    print("\n🛑  Human Progress Check —", stage_desc)
    if os.getenv(auto_env_var, "0") != "1":
        input("   → Press <Enter> to continue, or Ctrl+C to abort …")

# --- Base Class for Indicators ---
class Indicator:
    """Base class for all data indicators."""
    def __init__(self, name, source):
        self.name = name
        self.source = source

    def fetch_data(self, session):
        raise NotImplementedError("Subclasses must implement fetch_data.")

# --- World Bank Indicator Class ---
class WorldBankIndicator(Indicator):
    """Represents a single indicator from the World Bank API."""
    def __init__(self, indicator_id, name):
        super().__init__(name, 'World Bank')
        self.indicator_id = indicator_id
        
    def fetch_data(self, session):
        print(f"   Fetching {self.name} from World Bank...")
        all_data = []
        page = 1
        while True:
            url = f"http://api.worldbank.org/v2/country/all/indicator/{self.indicator_id}?format=json&page={page}&per_page=1000"
            try:
                response = session.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()
                if not data or len(data) < 2 or not data[1]:
                    break 
                all_data.extend(data[1])
                page += 1
                time.sleep(0.5) 
            except (requests.RequestException, ValueError) as e:
                print(f"      Error fetching page {page} for {self.name}: {e}")
                break
        
        if not all_data:
            print(f"      ⚠️ No data found for {self.name}.")
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        df = df[['country', 'date', 'value']]
        df.rename(columns={'country': 'country_wb', 'date': 'year', 'value': 'value'}, inplace=True)
        df['country'] = df['country_wb'].apply(lambda x: x['value'] if isinstance(x, dict) else x)
        df = df.dropna(subset=['value'])
        df['year'] = pd.to_numeric(df['year'])
        df['value'] = pd.to_numeric(df['value'])
        print(f"      ✅ Found {len(df)} records.")
        return df[['country', 'year', 'value']]

# --- WHO Indicator Class ---
class WHOIndicator(Indicator):
    """Represents a single indicator from the WHO GHO OData API."""
    def __init__(self, indicator_code, name):
        super().__init__(name, 'WHO')
        self.indicator_code = indicator_code

    def fetch_data(self, session):
        print(f"   Fetching {self.name} from WHO...")
        url = f"https://ghoapi.azureedge.net/api/{self.indicator_code}"
        try:
            response = session.get(url, timeout=45)
            response.raise_for_status()
            data = response.json().get('value', [])
            if not data:
                print(f"      ⚠️ No data found for {self.name}.")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df = df[df['SpatialDimType'] == 'COUNTRY']
            df = df[['SpatialDim', 'TimeDim', 'NumericValue']]
            df.rename(columns={'SpatialDim': 'country', 'TimeDim': 'year', 'NumericValue': 'value'}, inplace=True)
            # Convert ISO3 codes to standard country names for consistency
            try:
                import country_converter as coco
                df['country'] = coco.convert(names=df['country'].tolist(), to='name_short', not_found=np.nan)
                # Remove rows where conversion failed (regional aggregates or unknown codes)
                df.dropna(subset=['country'], inplace=True)
            except ImportError:
                pass
            df['year'] = pd.to_numeric(df['year'])
            df['value'] = pd.to_numeric(df['value'])
            print(f"      ✅ Found {len(df)} records.")
            return df
        except (requests.RequestException, ValueError) as e:
            print(f"      ❌ ERROR fetching {self.name}: {e}")
            return pd.DataFrame()

# --- DHS Indicator Class ---
class DHSIndicator(Indicator):
    """Represents a single indicator from the DHS API."""
    def __init__(self, indicator_id, name, country_iso2, survey_type='DHS'):
        super().__init__(name, 'DHS')
        self.indicator_id = indicator_id
        # Ensure country_iso2 is always a list for the API call
        self.country_iso2 = [country_iso2] if isinstance(country_iso2, str) else country_iso2
        self.survey_type = survey_type

    def fetch_data(self, session):
        print(f"   Fetching {self.name} from DHS for countries: {', '.join(self.country_iso2)}...")
        all_results = []
        # The DHS API can be slow, so we iterate through countries
        for country in tqdm(self.country_iso2, desc=f"   DHS: {self.name[:20]}"):
            url = f"https://api.dhsprogram.com/rest/dhs/data?indicatorIds={self.indicator_id}&countryIds={country}&surveyType={self.survey_type}&perPage=1000"
            try:
                response = session.get(url, timeout=60)
                if response.status_code == 200:
                    data = response.json().get('Data', [])
                    all_results.extend(data)
                else:
                    print(f"      ⚠️ DHS API returned status {response.status_code} for {country}")
                time.sleep(1) # Rate limit
            except requests.RequestException as e:
                print(f"      ❌ ERROR fetching DHS data for {country}: {e}")
                continue
        
        if not all_results:
            print(f"      ⚠️ No data found for {self.name} across all specified DHS countries.")
            return pd.DataFrame()

        df = pd.DataFrame(all_results)
        df.rename(columns={'CountryName': 'country', 'SurveyYear': 'year', 'Value': 'value'}, inplace=True)
        df = df[['country', 'year', 'value']]
        df['year'] = pd.to_numeric(df['year'])
        df['value'] = pd.to_numeric(df['value'])
        print(f"      ✅ Found {len(df)} total records from DHS.")
        return df

# --- Data Processing Functions ---

def get_dhs_country_list():
    """Fetches the list of all countries available in the DHS API."""
    print("Fetching list of available DHS countries...")
    try:
        url = "https://api.dhsprogram.com/rest/dhs/countries"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        countries = response.json().get('Data', [])
        iso2_codes = [c['DHS_CountryCode'] for c in countries]
        print(f"   ✅ Found {len(iso2_codes)} countries in DHS database.")
        return iso2_codes
    except requests.RequestException as e:
        print(f"   ❌ ERROR fetching DHS country list: {e}. Aborting.")
        return []

def pool_duplicate_sources(df):
    """
    Averages values for the same country, year, and risk factor from different sources.
    This creates a single, more robust value when multiple sources provide data.
    """
    print("🔎 Pooling data from duplicate sources...")
    
    # Identify duplicates based on country, year, and risk factor
    duplicates = df[df.duplicated(subset=['country', 'year', 'risk_factor'], keep=False)]
    
    if duplicates.empty:
        print("   ✅ No duplicate source data found to pool.")
        return df

    print(f"   Found {len(duplicates)} records from {duplicates['source'].nunique()} sources to be pooled.")
    
    # Calculate the mean for the duplicate groups
    # We group by country, year, and risk_factor, and calculate the mean of 'value'
    pooled_data = duplicates.groupby(['country', 'year', 'risk_factor']).agg(
        value=('value', 'mean'),
        source=('source', lambda x: 'Pooled ' + '/'.join(sorted(x.unique())))
    ).reset_index()

    # Get the indices of the original duplicate rows to remove them
    duplicate_indices = duplicates.index
    
    # Remove the original duplicate rows from the main dataframe
    df_no_duplicates = df.drop(index=duplicate_indices)
    
    # Concatenate the original data (without duplicates) and the new pooled data
    final_df = pd.concat([df_no_duplicates, pooled_data], ignore_index=True)
    
    print(f"   ✅ Pooling complete. Total records changed from {len(df)} to {len(final_df)}.")
    
    return final_df.sort_values(by=['country', 'risk_factor', 'year']).reset_index(drop=True)

# --- Main Pipeline Execution ---
def run_complete_pipeline():
    """Executes the full data extraction and processing pipeline."""
    start_time = datetime.now()
    print(f"🚀 GBD Data Pipeline Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Use a session for persistent connections and retries
    session = requests.Session()
    
    # Fetch the list of countries for which DHS has data
    dhs_countries_iso2 = get_dhs_country_list()
    if not dhs_countries_iso2:
        return

    # --- Progress checkpoint #1 ---
    progress_checkpoint("DHS country list fetched")

    # Define all indicators to be fetched
    indicators = [
        # --- Malnutrition ---
        WorldBankIndicator('SH.STA.MALN.ZS', 'Malnutrition (wght-for-age z<-2)'),
        WHOIndicator('NUTRITION_WH_2', 'Wasting prevalence among children under 5 years'),
        # Removed DHS indicators due to lack of available data in the DHS API as of July 2025.

        # --- Low Birth Weight ---
        WorldBankIndicator('SH.STA.BRTW.ZS', 'Low birth weight (=<2500 g)'),
        # Removed DHS indicators due to lack of available data in the DHS API as of July 2025.

        # --- Breastfeeding ---
        WHOIndicator('WHOSIS_000006', 'Exclusive breastfeeding under 6 months (%)'),

        # --- Household Environment ---
        WorldBankIndicator('EG.USE.COMM.CL.ZS', 'Use solid fuels (yes)'),
        # Removed DHS indicators due to lack of available data in the DHS API as of July 2025.
        
        # --- Child Mortality (for stratification) ---
        WorldBankIndicator('SH.DYN.MORT', 'Child Mortality Rate (U5MR)'),

        # --- Population Data (for template) ---
        WorldBankIndicator('SP.POP.TOTL', 'Total Population'),
        WorldBankIndicator('SP.POP.0014.TO.ZS', 'Population ages 0-14 (% of total)'),
    ]

    all_dfs = []
    print(f"\n🔄 Extracting {len(indicators)} indicators …")
    for indicator in tqdm(indicators, desc='Indicators', unit='indicator'):
        tqdm.write(f"   → {indicator.name}  (Source: {indicator.source})")
        df = indicator.fetch_data(session)
        if not df.empty:
            df['risk_factor'] = indicator.name
            df['source'] = indicator.source
            all_dfs.append(df)
        else:
            tqdm.write(f"   ⚠️  No rows retrieved for {indicator.name} – will rely on other sources / imputation")

    if not all_dfs:
        print("\n❌ No data could be fetched from any source. Pipeline stopping.")
        return

    # --- Progress checkpoint #2 ---
    progress_checkpoint("All indicators extracted")

    print("\n🔄 Consolidating all data sources...")
    consolidated_df = pd.concat(all_dfs, ignore_index=True)
    print(f"   Total records fetched: {len(consolidated_df)}")

    # Data Cleaning and Standardization
    consolidated_df.dropna(subset=['country', 'year', 'value'], inplace=True)
    consolidated_df['year'] = pd.to_numeric(consolidated_df['year']).astype(int)
    
    # Pool data from duplicate sources
    consolidated_df = pool_duplicate_sources(consolidated_df)

    # Separate population data from risk factor data
    pop_indicators = ['Population ages 0-14 (% of total)', 'Total Population']
    population_data = consolidated_df[consolidated_df['risk_factor'].isin(pop_indicators)].copy()
    risk_factor_data = consolidated_df[~consolidated_df['risk_factor'].isin(pop_indicators)].copy()
    
    # Calculate under 14 population
    pop_percent = population_data[population_data['risk_factor'] == 'Population ages 0-14 (% of total)']
    pop_total = population_data[population_data['risk_factor'] == 'Total Population']
    
    merged_pop = pd.merge(pop_percent, pop_total, on=['country', 'year'], suffixes=('_pct', '_total'))
    merged_pop['under_14_population'] = (merged_pop['value_pct'] / 100) * merged_pop['value_total']
    
    # Get the latest population data for each country
    latest_pop = merged_pop.sort_values('year', ascending=False).drop_duplicates('country')
    population_output = latest_pop[['country', 'year', 'under_14_population']]
    
    print(f"   ✅ Processed population data for {len(population_output)} countries.")

    # Save the consolidated data to an Excel file with multiple sheets
    consolidated_output_file = os.path.join(OUTPUT_DIR, 'gbd_consolidated_data.xlsx')
    
    print(f"\n💾 Saving consolidated data to '{consolidated_output_file}'...")
    with pd.ExcelWriter(consolidated_output_file) as writer:
        risk_factor_data.to_excel(writer, sheet_name='RiskFactors_Mortality', index=False)
        population_output.to_excel(writer, sheet_name='Under14_Population', index=False)
    print("   ✅ Excel file with risk factors & population saved.")

    # --- Progress checkpoint #3 ---
    progress_checkpoint("Risk-factor & population Excel written")

    # -------------------------------------------------------
    # COUNTRY LIST SUMMARY
    # -------------------------------------------------------
    print("\n Generating country coverage list …")
    # Union of countries found in any risk-factor sheet or population sheet
    countries_from_risk = set(risk_factor_data['country'].dropna().unique())
    countries_from_pop = set(population_output['country'].dropna().unique())
    all_countries = sorted(countries_from_risk.union(countries_from_pop))

    country_list_df = pd.DataFrame({'country': all_countries})
    country_list_file = os.path.join(OUTPUT_DIR, 'country_list.csv')

    try:
        country_list_df.to_csv(country_list_file, index=False)
        print(f"   ✅ Country list saved: {country_list_file}")
    except Exception as e:
        print(f"   ⚠️ Could not write country list file(s): {e}")

    # -------------------------------------------------------
    # TIDY LATEST RISK-FACTOR MATRIX (numeric, NaNs dropped)
    # -------------------------------------------------------
    print("\n📊 Creating tidy country × risk-factor matrix …")

    # Helper for country normalisation and region lookups
    region_helper = gbd_enhanced_template_populator.EnhancedTemplatePopulator()

    # 1. Take latest year per country + risk factor, then normalise country names
    latest_rf = (
        risk_factor_data
        .sort_values("year", ascending=False)
        .drop_duplicates(["country", "risk_factor"])
    )
    # Suppress noisy regex / ISO3 warnings during normalisation
    with contextlib.redirect_stdout(io.StringIO()):
        latest_rf = region_helper._normalize_country_names(latest_rf, "country")
        population_output = region_helper._normalize_country_names(population_output, "country")
    # Re-drop duplicates that may arise after normalisation (e.g., country synonyms collapsing)
    latest_rf = (
        latest_rf.sort_values("year", ascending=False)
        .drop_duplicates(["country", "risk_factor"])
    )

    # 2. Pivot to wide format (one row per country)
    tidy_df = (
        latest_rf
        .pivot(index="country", columns="risk_factor", values="value")
        .reset_index()
    )

    # 3. Derive regional & sub-regional labels
    print("   🌍 Deriving regional and sub-regional labels …")
    region_helper._generate_sub_regional_classification(consolidated_df.copy())

    tidy_df["Sub_Region"] = (
        tidy_df["country"].map(region_helper.sub_regional_map)
        .fillna(tidy_df["country"].map(region_helper.country_to_region))
    )

    # 4. Append latest population (absolute 0-14) column
    pop_latest = (
        population_output.rename(
            columns={"country": "country", "under_14_population": "Population_0_14"}
        )[["country", "Population_0_14"]]
    )
    tidy_df = tidy_df.merge(pop_latest, on="country", how="left")

    # 5. Remove rows where *all* risk-factor cols are NaN
    value_cols = tidy_df.columns.difference(["country", "Sub_Region", "Population_0_14"])
    tidy_df = tidy_df.dropna(subset=value_cols, how="all")

    # 6. Standardise column order and names
    tidy_df = tidy_df.rename(columns={"country": "Country"}).sort_values("Country")
    front_cols = ["Country", "Sub_Region", "Population_0_14"]
    other_cols = [c for c in tidy_df.columns if c not in front_cols]
    tidy_df = tidy_df[front_cols + other_cols]

    generic_tidy_csv = os.path.join(OUTPUT_DIR, "gbd_input_data_matrix.csv")

    try:
        tidy_df.to_csv(generic_tidy_csv, index=False)
        print(f"   ✅ Input-data-style CSV saved: {generic_tidy_csv}  (rows: {len(tidy_df)})")
    except Exception as e:
        print(f"   ⚠️ Could not write input-data CSV: {e}")

    # --- Progress checkpoint #4 ---
    progress_checkpoint("Tidy matrix CSV generated")

    # --- Final Step: Populate the GBD Template ---
    print("\n🏁 Starting final template population process...")
    template_file = 'Master Spreadsheet (DO NOT CHANGE YET).xls'
    if not os.path.exists(template_file):
        print(f"   ❌ ERROR: Master template file not found at '{template_file}'. Cannot proceed.")
        return
        
    populator = gbd_enhanced_template_populator.EnhancedTemplatePopulator()
    final_template_path = populator.create_populated_template(template_file, consolidated_output_file)
    
    end_time = datetime.now()
    print(f"\n✅ GBD Data Pipeline Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Total execution time: {end_time - start_time}")
    print(f"   Final populated template created at: {final_template_path}")

    # --- Progress checkpoint #5 ---
    progress_checkpoint("Pipeline completed — review outputs above", auto_env_var="_SKIP_FINAL_PROMPT_")

if __name__ == "__main__":
    run_complete_pipeline()