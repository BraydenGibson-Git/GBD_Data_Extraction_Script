import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def get_world_bank_population_data():
    """Get current population data for children 0-4 years from World Bank API."""
    print("🌍 Fetching current population data from World Bank...")
    
    try:
        # World Bank API for population ages 0-4
        url = "https://api.worldbank.org/v2/country/all/indicator/SP.POP.0004.TO?format=json&date=2022&per_page=300"
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if len(data) > 1:
            population_data = {}
            for item in data[1]:  # Data is in second element
                if item['value'] is not None:
                    country_code = item['countryiso3code']
                    country_name = item['country']['value']
                    population = item['value']
                    population_data[country_name] = {
                        'code': country_code,
                        'population_0_4': population,
                        'year': item['date']
                    }
            
            print(f"   ✅ Retrieved population data for {len(population_data)} countries")
            return population_data
        else:
            print("   ❌ No population data received")
            return {}
            
    except Exception as e:
        print(f"   ❌ Error fetching population data: {e}")
        return {}

def get_updated_regional_classifications():
    """Get updated regional classifications using World Bank regions and UN SDG regions."""
    print("🗺️  Setting up updated regional classifications...")
    
    # Modern World Bank regional classification (2023)
    wb_regions = {
        # Sub-Saharan Africa
        'SSA': ['Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi', 'Cameroon', 'Cape Verde', 
                'Central African Republic', 'Chad', 'Comoros', 'Congo, Dem. Rep.', 'Congo, Rep.', 
                'Cote d\'Ivoire', 'Equatorial Guinea', 'Eritrea', 'Eswatini', 'Ethiopia', 'Gabon', 
                'Gambia', 'Ghana', 'Guinea', 'Guinea-Bissau', 'Kenya', 'Lesotho', 'Liberia', 
                'Madagascar', 'Malawi', 'Mali', 'Mauritania', 'Mauritius', 'Mozambique', 'Namibia', 
                'Niger', 'Nigeria', 'Rwanda', 'Sao Tome and Principe', 'Senegal', 'Seychelles', 
                'Sierra Leone', 'Somalia', 'South Africa', 'South Sudan', 'Sudan', 'Tanzania', 
                'Togo', 'Uganda', 'Zambia', 'Zimbabwe'],
        
        # Middle East & North Africa  
        'MENA': ['Algeria', 'Bahrain', 'Djibouti', 'Egypt', 'Iran', 'Iraq', 'Israel', 'Jordan', 
                 'Kuwait', 'Lebanon', 'Libya', 'Malta', 'Morocco', 'Oman', 'Qatar', 'Saudi Arabia', 
                 'Syria', 'Tunisia', 'United Arab Emirates', 'West Bank and Gaza', 'Yemen'],
        
        # East Asia & Pacific
        'EAP': ['American Samoa', 'Australia', 'Brunei', 'Cambodia', 'China', 'Fiji', 'French Polynesia', 
                'Guam', 'Hong Kong', 'Indonesia', 'Japan', 'Kiribati', 'Korea, Rep.', 'Lao PDR', 
                'Macao SAR', 'Malaysia', 'Marshall Islands', 'Micronesia', 'Mongolia', 'Myanmar', 
                'Nauru', 'New Caledonia', 'New Zealand', 'Northern Mariana Islands', 'Palau', 
                'Papua New Guinea', 'Philippines', 'Samoa', 'Singapore', 'Solomon Islands', 
                'Thailand', 'Timor-Leste', 'Tonga', 'Tuvalu', 'Vanuatu', 'Vietnam'],
        
        # South Asia
        'SA': ['Afghanistan', 'Bangladesh', 'Bhutan', 'India', 'Maldives', 'Nepal', 'Pakistan', 'Sri Lanka'],
        
        # Europe & Central Asia
        'ECA': ['Albania', 'Armenia', 'Austria', 'Azerbaijan', 'Belarus', 'Belgium', 'Bosnia and Herzegovina', 
                'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic', 'Denmark', 'Estonia', 'Finland', 
                'France', 'Georgia', 'Germany', 'Greece', 'Hungary', 'Iceland', 'Ireland', 'Italy', 
                'Kazakhstan', 'Kosovo', 'Kyrgyz Republic', 'Latvia', 'Lithuania', 'Luxembourg', 
                'Moldova', 'Montenegro', 'Netherlands', 'North Macedonia', 'Norway', 'Poland', 
                'Portugal', 'Romania', 'Russian Federation', 'Serbia', 'Slovak Republic', 'Slovenia', 
                'Spain', 'Sweden', 'Switzerland', 'Tajikistan', 'Turkey', 'Turkmenistan', 'Ukraine', 
                'United Kingdom', 'Uzbekistan'],
        
        # Latin America & Caribbean
        'LAC': ['Antigua and Barbuda', 'Argentina', 'Bahamas', 'Barbados', 'Belize', 'Bolivia', 'Brazil', 
                'Chile', 'Colombia', 'Costa Rica', 'Cuba', 'Dominica', 'Dominican Republic', 'Ecuador', 
                'El Salvador', 'Grenada', 'Guatemala', 'Guyana', 'Haiti', 'Honduras', 'Jamaica', 
                'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Puerto Rico', 'St. Kitts and Nevis', 
                'St. Lucia', 'St. Vincent and the Grenadines', 'Suriname', 'Trinidad and Tobago', 
                'Uruguay', 'Venezuela'],
        
        # North America
        'NA': ['Canada', 'United States']
    }
    
    # Create reverse mapping
    country_to_region = {}
    for region, countries in wb_regions.items():
        for country in countries:
            country_to_region[country] = region
            
    # Add alternative country names for better matching
    alternative_names = {
        'Congo, Dem. Rep.': ['Democratic Republic of the Congo', 'Congo DRC', 'DRC'],
        'Congo, Rep.': ['Congo', 'Republic of the Congo'],
        'Cote d\'Ivoire': ['Ivory Coast'],
        'Iran': ['Iran (Islamic Republic of)'],
        'Korea, Rep.': ['South Korea', 'Republic of Korea'],
        'Lao PDR': ['Laos'],
        'Russian Federation': ['Russia'],
        'United States': ['United States of America', 'USA'],
        'United Kingdom': ['UK'],
        'Vietnam': ['Viet Nam']
    }
    
    for main_name, alternatives in alternative_names.items():
        if main_name in country_to_region:
            region = country_to_region[main_name]
            for alt_name in alternatives:
                country_to_region[alt_name] = region
    
    print(f"   ✅ Set up regional classifications for {len(country_to_region)} countries")
    return country_to_region

def standardize_country_name(country_name, population_data, country_to_region):
    """Try to match country name with population data and regional data."""
    if not country_name or pd.isna(country_name):
        return country_name, None, None
    
    country_str = str(country_name).strip()
    
    # Direct match
    if country_str in population_data:
        pop_data = population_data[country_str]
        region = country_to_region.get(country_str, 'Unknown')
        return country_str, pop_data, region
    
    # Try variations
    variations = [
        country_str.replace('Democratic Republic of the Congo', 'Congo, Dem. Rep.'),
        country_str.replace('Republic of the Congo', 'Congo, Rep.'),
        country_str.replace('Ivory Coast', 'Cote d\'Ivoire'),
        country_str.replace('South Korea', 'Korea, Rep.'),
        country_str.replace('North Korea', 'Korea, Dem. People\'s Rep.'),
        country_str.replace('Russia', 'Russian Federation'),
        country_str.replace('USA', 'United States'),
        country_str.replace('UK', 'United Kingdom'),
        country_str.replace('Viet Nam', 'Vietnam')
    ]
    
    for variation in variations:
        if variation in population_data:
            pop_data = population_data[variation]
            region = country_to_region.get(variation, 'Unknown')
            return variation, pop_data, region
    
    # Fuzzy matching
    for pop_country in population_data.keys():
        if country_str.lower() in pop_country.lower() or pop_country.lower() in country_str.lower():
            pop_data = population_data[pop_country]
            region = country_to_region.get(pop_country, 'Unknown')
            return pop_country, pop_data, region
    
    # No match found
    region = country_to_region.get(country_str, 'Unknown')
    return country_str, None, region

def load_master_template():
    """Load the master spreadsheet template."""
    print("📋 Loading master spreadsheet template...")
    
    try:
        df = pd.read_excel('Master Spreadsheet (DO NOT CHANGE YET).xls', sheet_name='ESTIMATES 2010-11')
        print(f"   ✅ Loaded template with {df.shape[0]} rows and {df.shape[1]} columns")
        return df
    except Exception as e:
        print(f"   ❌ Error loading template: {e}")
        return None

def load_gbd_data():
    """Load our extracted GBD data."""
    print("📊 Loading GBD extracted data...")
    
    try:
        gbd_data = pd.read_excel('gbd_processed_data/gbd_consolidated_data.xlsx', sheet_name='All_Data')
        print(f"   ✅ Loaded GBD data with {len(gbd_data)} records")
        print(f"   📋 Risk factors: {gbd_data['risk_factor'].unique()}")
        return gbd_data
    except Exception as e:
        print(f"   ❌ Error loading GBD data: {e}")
        return None

def calculate_country_prevalence_latest(country_data):
    """Calculate the most recent prevalence for a country from our GBD data."""
    if len(country_data) == 0:
        return None
    
    # Filter out NaN values
    valid_data = country_data[country_data['value'].notna()]
    if len(valid_data) == 0:
        return None
    
    # Use most recent year data
    if 'year' in valid_data.columns and valid_data['year'].notna().any():
        latest_year = valid_data['year'].max()
        latest_data = valid_data[valid_data['year'] == latest_year]
        return latest_data['value'].mean()
    else:
        return valid_data['value'].mean()

def populate_template_with_data(template_df, gbd_data, population_data, country_to_region):
    """Populate the master template with updated data."""
    print("\n🔧 Populating template with updated data...")
    
    # Find the country data section (starts at row 16, but 0-indexed is 15)
    country_start_row = 15
    
    # Create a copy of the template
    new_df = template_df.copy()
    
    # Risk factor mapping
    risk_factor_mapping = {
        'Malnutrition (wght-for-age z<-2)': 3,  # Column D (% Malnutr)
        'Low birth weight (=<2500 g)': 4,       # Column E (% LBW)
        'Non-breastfed exclus. (4 mths)': 5,   # Column F (% Non-BF)
        'Use solid fuels (yes)': 6,             # Column G (% Sol-Fuels)
        'Crowding (5 or more persons)': 7       # Column H (% Crowd) - Note: template has "7 or more"
    }
    
    updated_countries = 0
    missing_population = 0
    missing_prevalence = 0
    
    # Process each country
    for i in range(country_start_row + 1, len(new_df)):
        country_name = new_df.iloc[i, 0]  # Column A
        
        if pd.isna(country_name) or not isinstance(country_name, str):
            continue
            
        if len(str(country_name).strip()) < 2:
            continue
            
        print(f"   🔄 Processing: {country_name}")
        
        # Standardize country name and get data
        std_name, pop_data, region = standardize_country_name(country_name, population_data, country_to_region)
        
        # Update population data (Column B)
        if pop_data:
            new_df.iloc[i, 1] = pop_data['population_0_4']
            print(f"      📊 Updated population: {pop_data['population_0_4']:,}")
        else:
            missing_population += 1
            print(f"      ⚠️  No population data found")
        
        # Update region (Column C)
        if region and region != 'Unknown':
            new_df.iloc[i, 2] = region
            print(f"      🗺️  Updated region: {region}")
        
        # Update prevalence data for each risk factor
        prevalence_updated = 0
        for gbd_risk_factor, col_idx in risk_factor_mapping.items():
            country_risk_data = gbd_data[
                (gbd_data['risk_factor'] == gbd_risk_factor) & 
                (gbd_data['country'].str.contains(std_name, case=False, na=False))
            ]
            
            if len(country_risk_data) > 0:
                prevalence = calculate_country_prevalence_latest(country_risk_data)
                if prevalence is not None:
                    new_df.iloc[i, col_idx] = round(prevalence, 1)
                    prevalence_updated += 1
        
        if prevalence_updated > 0:
            print(f"      ✅ Updated {prevalence_updated} prevalence values")
        else:
            missing_prevalence += 1
            print(f"      ⚠️  No prevalence data found")
        
        updated_countries += 1
    
    print(f"\n📋 Summary:")
    print(f"   ✅ Countries processed: {updated_countries}")
    print(f"   📊 Missing population data: {missing_population}")
    print(f"   📈 Missing prevalence data: {missing_prevalence}")
    
    return new_df

def create_populated_master_spreadsheet():
    """Main function to create populated master spreadsheet."""
    print("🎯 === POPULATING MASTER SPREADSHEET TEMPLATE ===")
    print(f"Started at: {datetime.now()}")
    
    # Load all data sources
    template_df = load_master_template()
    if template_df is None:
        return
    
    gbd_data = load_gbd_data()
    if gbd_data is None:
        return
    
    population_data = get_world_bank_population_data()
    country_to_region = get_updated_regional_classifications()
    
    # Populate the template
    populated_df = populate_template_with_data(template_df, gbd_data, population_data, country_to_region)
    
    # Save the populated template
    output_file = 'GBD_Master_Spreadsheet_Updated.xlsx'
    
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            populated_df.to_excel(writer, sheet_name='ESTIMATES_Updated', index=False)
            
            # Also copy supplementary info if it exists
            try:
                supp_df = pd.read_excel('Master Spreadsheet (DO NOT CHANGE YET).xls', sheet_name='Supplementary info')
                supp_df.to_excel(writer, sheet_name='Supplementary info', index=False)
            except:
                pass
        
        print(f"\n🎉 Updated master spreadsheet saved as: {output_file}")
        
        # Create summary report
        create_update_summary(populated_df, population_data, country_to_region)
        
    except Exception as e:
        print(f"❌ Error saving file: {e}")

def create_update_summary(populated_df, population_data, country_to_region):
    """Create summary of the update process."""
    print("\n📊 Creating update summary...")
    
    # Count regional distribution
    region_counts = {}
    total_pop = 0
    
    country_start_row = 15
    for i in range(country_start_row + 1, len(populated_df)):
        country = populated_df.iloc[i, 0]
        region = populated_df.iloc[i, 2]
        population = populated_df.iloc[i, 1]
        
        if pd.notna(country) and isinstance(country, str) and len(str(country).strip()) > 1:
            if pd.notna(region):
                region_counts[region] = region_counts.get(region, 0) + 1
            if pd.notna(population) and isinstance(population, (int, float)):
                total_pop += population
    
    summary_data = {
        'Update_Date': datetime.now().strftime('%Y-%m-%d'),
        'Total_Countries': len([c for c in populated_df.iloc[country_start_row+1:, 0] if pd.notna(c) and isinstance(c, str) and len(str(c).strip()) > 1]),
        'Population_Data_Source': 'World Bank 2022',
        'Regional_Classification': 'World Bank Regions 2023',
        'Total_Population_0_4': int(total_pop) if total_pop > 0 else 'Not calculated',
        'Regional_Distribution': region_counts,
        'Data_Sources_Used': 'DHS, WHO, UNICEF MICS',
        'GBD_Data_Year_Range': '1986-2023'
    }
    
    # Save summary
    summary_df = pd.DataFrame([summary_data])
    summary_df.to_excel('GBD_Update_Summary.xlsx', index=False)
    
    print(f"📋 Update summary:")
    print(f"   📅 Update date: {summary_data['Update_Date']}")
    print(f"   🌍 Total countries: {summary_data['Total_Countries']}")
    print(f"   👶 Total population 0-4: {summary_data['Total_Population_0_4']:,}" if isinstance(summary_data['Total_Population_0_4'], int) else f"   👶 Total population 0-4: {summary_data['Total_Population_0_4']}")
    print(f"   🗺️  Regional distribution: {region_counts}")
    print(f"   💾 Summary saved as: GBD_Update_Summary.xlsx")

if __name__ == "__main__":
    create_populated_master_spreadsheet() 