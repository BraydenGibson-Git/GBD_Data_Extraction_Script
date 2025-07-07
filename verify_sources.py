import requests
import pandas as pd

# --- Configuration ---
DHS_INDICATORS = {
    'CH_MANU_C_WH2': 'Malnutrition (wght-for-age z<-2)',
    'RH_BF_C_LOW': 'Low birth weight (=<2500 g)',
    'HC_TIME_C_WSD': 'Crowding (5 or more persons)',
}

WHO_INDICATORS = {
    'NUTRITION_WASTING': 'Malnutrition (wght-for-age z<-2)',
    'NUTRITION_NBF4M_PER': 'Non-breastfed exclus. (4 mths)',
}

WB_INDICATORS = {
    'SH.STA.MALN.ZS': 'Malnutrition (wght-for-age z<-2)',
    'SH.STA.BRTW.ZS': 'Low birth weight (=<2500 g)',
    'EG.USE.COMM.CL.ZS': 'Use solid fuels (yes)',
    'SH.DYN.MORT': 'Child Mortality Rate (U5MR)',
    'SP.POP.0-14.TO.ZS': 'Population ages 0-14 (% of total)',
    'SP.POP.TOTL': 'Total Population',
}

# --- Verification Functions ---

def verify_dhs():
    print("\\n--- Verifying DHS Program API ---")
    base_url = "https://api.dhsprogram.com/rest/dhs/data"
    for indicator, name in DHS_INDICATORS.items():
        print(f"Checking {indicator} ({name})...")
        try:
            url = f"{base_url}?indicatorIds={indicator}&f=json&perPage=1"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'Data' in data and len(data['Data']) > 0:
                    print("  ✅ OK: Data found.")
                    print(f"  Structure: {list(data['Data'][0].keys())}")
                else:
                    print("  ❌ FAILED: API returned no data for this indicator.")
            else:
                print(f"  ❌ FAILED: HTTP Status {response.status_code}")
        except Exception as e:
            print(f"  ❌ FAILED: Request error - {e}")

def verify_who():
    print("\\n--- Verifying WHO GHO API ---")
    base_url = "https://ghoapi.azureedge.net/api"
    for indicator, name in WHO_INDICATORS.items():
        print(f"Checking {indicator} ({name})...")
        try:
            url = f"{base_url}/{indicator}"
            # Can't limit to 1 record, so we just get the whole thing
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'value' in data and len(data['value']) > 0:
                    print("  ✅ OK: Data found.")
                    print(f"  Structure: {list(data['value'][0].keys())}")
                else:
                    print("  ❌ FAILED: API returned no data for this indicator.")
            else:
                print(f"  ❌ FAILED: HTTP Status {response.status_code}")
        except Exception as e:
            print(f"  ❌ FAILED: Request error - {e}")

def verify_world_bank():
    print("\\n--- Verifying World Bank API ---")
    base_url = "http://api.worldbank.org/v2"
    for indicator, name in WB_INDICATORS.items():
        print(f"Checking {indicator} ({name})...")
        try:
            url = f"{base_url}/country/all/indicator/{indicator}?format=json&per_page=1"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 1 and data[1]:
                    print("  ✅ OK: Data found.")
                    print(f"  Structure: {list(data[1][0].keys())}")
                else:
                    print("  ❌ FAILED: API returned no data for this indicator.")
            else:
                print(f"  ❌ FAILED: HTTP Status {response.status_code}")
        except Exception as e:
            print(f"  ❌ FAILED: Request error - {e}")

if __name__ == '__main__':
    print("--- Starting Data Source and Structure Verification ---")
    verify_dhs()
    verify_who()
    verify_world_bank()
    print("\\n--- Verification Complete ---") 