import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def get_updated_regional_classifications():
    """Get updated regional classifications using World Bank regions."""
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
        'Congo, Dem. Rep.': ['Democratic Republic of the Congo', 'Congo DRC', 'DRC', 'Dem. Rep. of the Congo'],
        'Congo, Rep.': ['Congo', 'Republic of the Congo'],
        'Cote d\'Ivoire': ['Ivory Coast', 'Côte d\'Ivoire'],
        'Iran': ['Iran (Islamic Republic of)'],
        'Korea, Rep.': ['South Korea', 'Republic of Korea'],
        'Lao PDR': ['Laos', 'Lao People\'s Dem. Republic'],
        'Russian Federation': ['Russia'],
        'United States': ['United States of America', 'USA'],
        'United Kingdom': ['UK'],
        'Vietnam': ['Viet Nam'],
        'Syria': ['Syrian Arab Republic'],
        'Libya': ['Libyan Arab Jamahiriya'],
        'North Korea': ['Dem. Peoples\'s Rep. of Korea'],
        'Tanzania': ['United Republic of Tanzania'],
        'Eswatini': ['Swaziland'],
        'Timor-Leste': ['Timor Leste'],
        'Micronesia': ['Micronesia (Fed. States of)']
    }
    
    for main_name, alternatives in alternative_names.items():
        if main_name in country_to_region:
            region = country_to_region[main_name]
            for alt_name in alternatives:
                country_to_region[alt_name] = region
    
    print(f"   ✅ Set up regional classifications for {len(country_to_region)} countries")
    return country_to_region

def standardize_country_name_for_gbd(country_name, gbd_data):
    """Match country name with GBD data."""
    if not country_name or pd.isna(country_name):
        return country_name, []
    
    country_str = str(country_name).strip()
    
    # Get unique countries from GBD data (filter out NaN values)
    gbd_countries = gbd_data['country'].dropna().unique()
    
    # Direct match
    exact_matches = [c for c in gbd_countries if isinstance(c, str) and c.lower() == country_str.lower()]
    if exact_matches:
        return exact_matches[0], gbd_data[gbd_data['country'] == exact_matches[0]]
    
    # Fuzzy matching
    fuzzy_matches = [c for c in gbd_countries if isinstance(c, str) and (country_str.lower() in c.lower() or c.lower() in country_str.lower())]
    if fuzzy_matches:
        # Use the best match (shortest name that contains the search term)
        best_match = min(fuzzy_matches, key=len)
        return best_match, gbd_data[gbd_data['country'] == best_match]
    
    # No match found
    return country_str, []

def calculate_country_prevalence_latest(country_data):
    """Calculate the most recent prevalence for a country from our GBD data."""
    if len(country_data) == 0:
        return None, None, None
    
    # Filter out NaN values
    valid_data = country_data[country_data['value'].notna()]
    if len(valid_data) == 0:
        return None, None, None
    
    # Use most recent year data
    if 'year' in valid_data.columns and valid_data['year'].notna().any():
        latest_year = valid_data['year'].max()
        latest_data = valid_data[valid_data['year'] == latest_year]
        mean_value = latest_data['value'].mean()
        
        # Get confidence interval if available
        ci_info = None
        if 'confidence_intervals' in latest_data.columns:
            ci_vals = latest_data['confidence_intervals'].dropna()
            if len(ci_vals) > 0:
                ci_info = ci_vals.iloc[0]
                
        return round(mean_value, 1), latest_year, ci_info
    else:
        mean_value = valid_data['value'].mean()
        return round(mean_value, 1), None, None

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
        print(f"   📋 Risk factors: {sorted(gbd_data['risk_factor'].unique())}")
        print(f"   🌍 Countries: {len(gbd_data['country'].unique())} unique countries")
        print(f"   📅 Year range: {gbd_data['year'].min()} - {gbd_data['year'].max()}")
        return gbd_data
    except Exception as e:
        print(f"   ❌ Error loading GBD data: {e}")
        return None

def create_final_populated_template():
    """Create the final populated template with all improvements."""
    print("🎯 === CREATING FINAL POPULATED MASTER TEMPLATE ===")
    print(f"Started at: {datetime.now()}")
    
    # Load data sources
    template_df = load_master_template()
    if template_df is None:
        return
    
    gbd_data = load_gbd_data()
    if gbd_data is None:
        return
    
    country_to_region = get_updated_regional_classifications()
    
    print("\n🔧 Processing template data...")
    
    # Find the country data section (starts at row 16, but 0-indexed is 15)
    country_start_row = 15
    
    # Create a copy of the template
    new_df = template_df.copy()
    
    # Risk factor mapping (column indices)
    risk_factor_mapping = {
        'Malnutrition (wght-for-age z<-2)': 3,  # Column D (% Malnutr)
        'Low birth weight (=<2500 g)': 4,       # Column E (% LBW)
        'Non-breastfed exclus. (4 mths)': 5,   # Column F (% Non-BF)
        'Use solid fuels (yes)': 6,             # Column G (% Sol-Fuels)
        'Crowding (5 or more persons)': 7       # Column H (% Crowd)
    }
    
    # Statistics tracking
    stats = {
        'total_countries': 0,
        'regions_updated': 0,
        'prevalence_updated': 0,
        'population_preserved': 0,
        'countries_with_data': set(),
        'updated_data': []
    }
    
    # Process each country
    for i in range(country_start_row + 1, len(new_df)):
        country_name = new_df.iloc[i, 0]  # Column A
        
        if pd.isna(country_name) or not isinstance(country_name, str):
            continue
            
        if len(str(country_name).strip()) < 2:
            continue
            
        # Skip summary/calculation rows
        if any(skip_word in str(country_name).lower() for skip_word in ['risk', 'comparison', 'population', 'incidence', 'severe', 'malnutrition', 'birth', 'breastfed', 'fuel', 'crowd']):
            continue
            
        stats['total_countries'] += 1
        print(f"   🔄 Processing: {country_name}")
        
        # Check if population data exists and preserve it
        existing_pop = new_df.iloc[i, 1]  # Column B
        if pd.notna(existing_pop) and isinstance(existing_pop, (int, float)) and existing_pop > 0:
            stats['population_preserved'] += 1
            print(f"      📊 Preserved population: {existing_pop:,.0f}")
        
        # Update region classification
        region = country_to_region.get(country_name, 'Unknown')
        if region != 'Unknown':
            old_region = new_df.iloc[i, 2]  # Column C
            new_df.iloc[i, 2] = region
            stats['regions_updated'] += 1
            print(f"      🗺️  Updated region: {old_region} → {region}")
        
        # Match with GBD data and update prevalence
        matched_name, country_gbd_data = standardize_country_name_for_gbd(country_name, gbd_data)
        
        if len(country_gbd_data) > 0:
            stats['countries_with_data'].add(matched_name)
            prevalence_updates = []
            
            # Update prevalence data for each risk factor
            for gbd_risk_factor, col_idx in risk_factor_mapping.items():
                risk_factor_data = country_gbd_data[country_gbd_data['risk_factor'] == gbd_risk_factor]
                
                if len(risk_factor_data) > 0:
                    prevalence, year, ci = calculate_country_prevalence_latest(risk_factor_data)
                    if prevalence is not None:
                        old_value = new_df.iloc[i, col_idx]
                        new_df.iloc[i, col_idx] = prevalence
                        
                        prevalence_updates.append({
                            'risk_factor': gbd_risk_factor,
                            'old_value': old_value,
                            'new_value': prevalence,
                            'year': year,
                            'confidence_interval': ci
                        })
            
            if prevalence_updates:
                stats['prevalence_updated'] += 1
                stats['updated_data'].append({
                    'country': country_name,
                    'matched_gbd_name': matched_name,
                    'updates': prevalence_updates
                })
                print(f"      ✅ Updated {len(prevalence_updates)} prevalence values from GBD data")
            else:
                print(f"      ⚠️  GBD data found but no matching risk factors")
        else:
            print(f"      ⚠️  No GBD data found")
    
    # Save the populated template
    output_file = 'GBD_Final_Master_Template.xlsx'
    
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Main data sheet
            new_df.to_excel(writer, sheet_name='ESTIMATES_Updated', index=False)
            
            # Create detailed update log
            if stats['updated_data']:
                update_log = []
                for country_update in stats['updated_data']:
                    for update in country_update['updates']:
                        update_log.append({
                            'Country': country_update['country'],
                            'GBD_Matched_Name': country_update['matched_gbd_name'],
                            'Risk_Factor': update['risk_factor'],
                            'Old_Value': update['old_value'],
                            'New_Value': update['new_value'],
                            'Data_Year': update['year'],
                            'Confidence_Interval': update['confidence_interval']
                        })
                
                update_df = pd.DataFrame(update_log)
                update_df.to_excel(writer, sheet_name='Update_Log', index=False)
            
            # Copy supplementary info if it exists
            try:
                supp_df = pd.read_excel('Master Spreadsheet (DO NOT CHANGE YET).xls', sheet_name='Supplementary info')
                supp_df.to_excel(writer, sheet_name='Supplementary info', index=False)
            except:
                pass
        
        print(f"\n🎉 Final master template saved as: {output_file}")
        
        # Create comprehensive summary
        create_comprehensive_summary(stats, country_to_region)
        
    except Exception as e:
        print(f"❌ Error saving file: {e}")

def create_comprehensive_summary(stats, country_to_region):
    """Create comprehensive summary of the update process."""
    print("\n📊 Creating comprehensive summary...")
    
    # Regional distribution
    region_dist = {}
    for country_update in stats['updated_data']:
        country = country_update['country']
        region = country_to_region.get(country, 'Unknown')
        region_dist[region] = region_dist.get(region, 0) + 1
    
    # Risk factor update counts
    risk_factor_counts = {}
    for country_update in stats['updated_data']:
        for update in country_update['updates']:
            rf = update['risk_factor']
            risk_factor_counts[rf] = risk_factor_counts.get(rf, 0) + 1
    
    summary_data = {
        'Update_Date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'Template_Source': 'Master Spreadsheet (DO NOT CHANGE YET).xls',
        'GBD_Data_Source': 'gbd_processed_data/gbd_consolidated_data.xlsx',
        'Total_Countries_Processed': stats['total_countries'],
        'Regions_Updated': stats['regions_updated'],
        'Countries_With_Prevalence_Updates': stats['prevalence_updated'],
        'Population_Data_Preserved': stats['population_preserved'],
        'Unique_GBD_Countries_Matched': len(stats['countries_with_data']),
        'Regional_Classification': 'World Bank Regions 2023',
        'Updated_Countries_By_Region': region_dist,
        'Risk_Factor_Update_Counts': risk_factor_counts,
        'GBD_Countries_Matched': sorted(list(stats['countries_with_data']))
    }
    
    # Save summary
    summary_df = pd.DataFrame([summary_data])
    summary_df.to_excel('GBD_Final_Update_Summary.xlsx', index=False)
    
    print(f"📋 Final Update Summary:")
    print(f"   📅 Update completed: {summary_data['Update_Date']}")
    print(f"   🌍 Countries processed: {summary_data['Total_Countries_Processed']}")
    print(f"   🗺️  Regions updated: {summary_data['Regions_Updated']}")
    print(f"   📈 Countries with prevalence updates: {summary_data['Countries_With_Prevalence_Updates']}")
    print(f"   👶 Population data preserved: {summary_data['Population_Data_Preserved']}")
    print(f"   🎯 GBD countries matched: {summary_data['Unique_GBD_Countries_Matched']}")
    print(f"   🗺️  Updated by region: {region_dist}")
    print(f"   📊 Risk factor updates: {risk_factor_counts}")
    print(f"   💾 Summary saved as: GBD_Final_Update_Summary.xlsx")

if __name__ == "__main__":
    create_final_populated_template() 