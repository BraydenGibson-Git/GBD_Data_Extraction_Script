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
import tempfile, hashlib

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

# --- UN-Habitat Indicator Class ---
class UNHabitatIndicator(Indicator):
    """Crowding indicator from UN-Habitat (SDG 11.1.1 component).

    Data source: HDX dataset "Access to basic services in cities and urban areas".
    The file contains column `Sufficient living area (%)`; we convert to
    overcrowding percentage = 100 – sufficient.
    """

    DATASET_SLUG = "basic-services"  # HDX dataset slug on HDX
    RESOURCE_NAME_KEYWORDS = [
        "access_to_basic_services",  # appears in file name on HDX
        "basic_services", "living_area"]

    def __init__(self, name: str = "Crowding (% lacking sufficient living area)"):
        super().__init__(name, "UN-Habitat")

    @staticmethod
    def _find_resource(download_meta):
        """Pick the first resource URL that looks like the CSV we need."""
        for res in download_meta.get("resources", []):
            title = (res.get("name") or "") + " " + (res.get("description") or "")
            fn = res.get("url") or res.get("download_url")
            if fn and any(k in title.lower() or k in fn.lower() for k in UNHabitatIndicator.RESOURCE_NAME_KEYWORDS):
                return fn
        return None

    def _download_file(self) -> str:
        """Download the dataset resource (CSV or XLSX) to a temp file and return the path."""
        api_url = f"https://data.humdata.org/api/3/action/package_show?id={self.DATASET_SLUG}"
        try:
            meta = requests.get(api_url, timeout=45).json()
            if not meta.get("success"):
                raise ValueError("HDX API did not return success flag")
            resource_url = self._find_resource(meta["result"])
            if not resource_url:
                raise ValueError("Could not locate suitable resource in HDX dataset")
            raw_bytes = requests.get(resource_url, timeout=90).content
            ext = ".xlsx" if resource_url.lower().endswith("xlsx") else ".csv"
            fp = os.path.join(tempfile.gettempdir(), hashlib.md5(resource_url.encode()).hexdigest() + ext)
            with open(fp, "wb") as f:
                f.write(raw_bytes)
            return fp
        except Exception as e:
            print(f"      ❌ ERROR fetching UN-Habitat dataset: {e}")
            return ""

    def fetch_data(self, session):
        print(f"   Fetching {self.name} from UN-Habitat HDX…")
        file_path = self._download_file()
        if not file_path or not os.path.exists(file_path):
            return pd.DataFrame()
        try:
            if file_path.endswith(".csv"):
                df = pd.read_csv(file_path, low_memory=False)
            else:
                # The XLSX file has two sheets; data is in '2-Data'. The first ~11 rows are metadata.
                # We'll let pandas figure out header by auto-detection: find the row with 'Country / Territor'
                tmp_df = pd.read_excel(file_path, sheet_name="2-Data", header=None)
                header_row_idx = tmp_df.apply(lambda r: r.astype(str).str.contains("Sufficient living area", case=False, na=False).any(), axis=1)
                header_indices = header_row_idx[header_row_idx].index
                if len(header_indices):
                    idx = header_indices[0]
                    tmp_df.columns = tmp_df.iloc[idx]
                    df = tmp_df.drop(index=range(0, idx+1))
                else:
                    df = tmp_df
        except Exception as e:
            print(f"      ❌ ERROR reading UN-Habitat file: {e}")
            return pd.DataFrame()

        # Expect columns: Country, Year, Sufficient living area (%)
        # Keep numeric rows only
        if "Sufficient living area (%)" not in df.columns:
            # Try alternative column naming – some columns may be non-string
            suff_cols = [c for c in df.columns if isinstance(c, str) and "sufficient" in c.lower() and "%" in c]
            if not suff_cols:
                print("      ⚠️ Column with sufficient living area not found.")
                return pd.DataFrame()
            target_col = suff_cols[0]
        else:
            target_col = "Sufficient living area (%)"

        df = df.rename(columns={target_col: "sufficient"})
        # Convert to numeric
        df["sufficient"] = pd.to_numeric(df["sufficient"], errors="coerce")
        df.dropna(subset=["sufficient"], inplace=True)

        # Overcrowding percentage
        df["value"] = 100 - df["sufficient"]

        # Dynamically detect country & year column names
        country_cols = [c for c in df.columns if isinstance(c,str) and "country" in c.lower() and "name" in c.lower()]
        if not country_cols:
            country_cols = [c for c in df.columns if isinstance(c,str) and "country" in c.lower()]
        year_cols = [c for c in df.columns if isinstance(c,str) and "year" in c.lower()]
        if not country_cols or not year_cols:
            print("      ⚠️ Could not locate country/year columns in UN-Habitat data.")
            return pd.DataFrame()
        df.rename(columns={country_cols[0]: "country", year_cols[0]: "year"}, inplace=True)

        # Keep only needed cols
        df = df[["country", "year", "value"]]

        # Normalise country names
        try:
            import country_converter as coco, numpy as np
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                df["country"] = coco.convert(names=df["country"].tolist(), to="name_short", not_found=np.nan)
            df.dropna(subset=["country"], inplace=True)
        except ImportError:
            pass

        print(f"      ✅ Found {len(df)} records.")
        return df

# --- UNICEF Under-5 Population Indicator ---
class UNICEFUnder5PopIndicator(Indicator):
    """Fetches absolute under-5 population counts (0-4 years) from UNICEF SDMX."""

    ENDPOINT = "https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/UNICEF,DM,1.0/.DM_POP_U5?format=sdmx-json"

    def __init__(self):
        super().__init__("Population ages 0-4 (number)", "UNICEF")

    def fetch_data(self, session):
        print("   Fetching Under-5 population from UNICEF SDMX …")
        try:
            resp = session.get(self.ENDPOINT, timeout=90)
            resp.raise_for_status()
            payload = resp.json()

            # Build lookup tables for REF_AREA and TIME_PERIOD indices
            series_dims = payload["data"]["structure"]["dimensions"]["series"]
            ref_areas = series_dims[0]["values"]  # index 0 is REF_AREA
            ref_lookup = {str(idx): v["id"] for idx, v in enumerate(ref_areas)}

            time_values = payload["data"]["structure"]["dimensions"]["observation"][0]["values"]
            time_lookup = {str(idx): int(v["id"]) for idx, v in enumerate(time_values)}

            series_dict = payload["data"]["dataSets"][0]["series"]

            records = []
            for s_key, s_val in series_dict.items():
                ref_idx = s_key.split(":")[0]
                iso3 = ref_lookup.get(ref_idx)
                if not iso3:
                    continue
                for t_idx, obs in s_val["observations"].items():
                    year = time_lookup.get(t_idx)
                    if year is None:
                        continue
                    value = obs[0] * 1000  # API returns thousands of persons
                    records.append({"country": iso3, "year": year, "value": value})

            if not records:
                print("      ⚠️ No records parsed from UNICEF response.")
                return pd.DataFrame()

            df = pd.DataFrame(records)
            # Convert ISO3 to short names for consistency
            try:
                import country_converter as coco
                df["country"] = coco.convert(df["country"].tolist(), to="name_short", not_found=np.nan)
                df.dropna(subset=["country"], inplace=True)
            except ImportError:
                pass

            print(f"      ✅ Parsed {len(df)} UNICEF under-5 records.")
            return df
        except Exception as e:
            print(f"      ❌ ERROR fetching UNICEF U5 population: {e}")
            return pd.DataFrame()

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

        # --- Crowding & Housing ---
        UNHabitatIndicator(),
        WorldBankIndicator('EN.POP.SLUM.UR.ZS', 'Urban slum population (% of urban)'),

        # --- Population Data (absolute counts 0-4) ---
        UNICEFUnder5PopIndicator(),
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

    # --- Ensure country column is hashable (no list objects) ---
    consolidated_df['country'] = consolidated_df['country'].apply(lambda x: x[0] if isinstance(x, list) else x)

    # Data Cleaning and Standardization
    consolidated_df.dropna(subset=['country', 'year', 'value'], inplace=True)
    consolidated_df['year'] = pd.to_numeric(consolidated_df['year']).astype(int)
    
    # Ensure numeric values; coerce errors to NaN then drop
    consolidated_df['value'] = pd.to_numeric(consolidated_df['value'], errors='coerce')

    # Pool data from duplicate sources
    consolidated_df = pool_duplicate_sources(consolidated_df)

    # Separate population data from risk factor data (only absolute under-5 counts)
    pop_indicators = ['Population ages 0-4 (number)']
    population_data = consolidated_df[consolidated_df['risk_factor'].isin(pop_indicators)].copy()
    risk_factor_data = consolidated_df[~consolidated_df['risk_factor'].isin(pop_indicators)].copy()
    
    # Already have absolute counts; just take latest year per country
    latest_pop = (
        population_data
        .sort_values('year', ascending=False)
        .drop_duplicates('country')
    )
    population_output = latest_pop[['country', 'year', 'value']].rename(columns={'value': 'under_5_population'})
    
    print(f"   ✅ Processed population data for {len(population_output)} countries.")

    # Save the consolidated data to an Excel file with multiple sheets
    consolidated_output_file = os.path.join(OUTPUT_DIR, 'gbd_consolidated_data.xlsx')
    
    print(f"\n💾 Saving consolidated data to '{consolidated_output_file}'...")
    with pd.ExcelWriter(consolidated_output_file) as writer:
        risk_factor_data.to_excel(writer, sheet_name='RiskFactors_Mortality', index=False)
        population_output.to_excel(writer, sheet_name='Under5_Population', index=False)
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

    # 4. Append latest population (absolute 0-4) column
    pop_latest = (
        population_output.rename(
            columns={"country": "country", "under_5_population": "Population_0_4"}
        )[["country", "Population_0_4"]]
    )
    tidy_df = tidy_df.merge(pop_latest, on="country", how="left")

    # 5. Remove rows where *all* risk-factor cols are NaN
    value_cols = tidy_df.columns.difference(["country", "Sub_Region", "Population_0_4"])
    tidy_df = tidy_df.dropna(subset=value_cols, how="all")

    # 6. Standardise column order and names
    tidy_df = tidy_df.rename(columns={"country": "Country"}).sort_values("Country")
    front_cols = ["Country", "Sub_Region", "Population_0_4"]
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