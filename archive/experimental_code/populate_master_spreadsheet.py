import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import PatternFill, Font
import re
from datetime import datetime

def load_master_template():
    """Load the master spreadsheet template."""
    print("📋 Loading master spreadsheet template...")
    
    # Read the assignment sheet
    assignment_df = pd.read_excel('Prevalence Data Sources.xlsx', sheet_name='Assignment')
    
    # Read all prevalence sheets
    xl_file = pd.ExcelFile('Prevalence Data Sources.xlsx')
    prevalence_sheets = {}
    
    for sheet_name in xl_file.sheet_names:
        if sheet_name != 'Assignment':
            df = pd.read_excel('Prevalence Data Sources.xlsx', sheet_name=sheet_name)
            prevalence_sheets[sheet_name] = df
            
    return assignment_df, prevalence_sheets

def load_gbd_data():
    """Load our extracted GBD data."""
    print("📊 Loading GBD extracted data...")
    
    # Read the consolidated GBD data
    gbd_data = pd.read_excel('gbd_processed_data/gbd_consolidated_data.xlsx', sheet_name='All_Data')
    
    print(f"   Loaded {len(gbd_data)} records")
    print(f"   Risk factors: {gbd_data['risk_factor'].unique()}")
    print(f"   Data sources: {gbd_data['data_source'].unique()}")
    
    return gbd_data

def map_risk_factor_sheets(gbd_data, prevalence_sheets):
    """Map GBD risk factors to master spreadsheet sheets."""
    
    # Create mapping between GBD risk factors and sheet names
    risk_factor_mapping = {
        'Malnutrition (wght-for-age z<-2)': 'Malnutrition (wght-for-age z<-2',
        'Low birth weight (=<2500 g)': 'Low Birth Weight',
        'Non-breastfed exclus. (4 mths)': 'Non-breastfed exclus. (4 mths)',
        'Use solid fuels (yes)': 'Use solid fuels (yes)',
        'Crowding (5 or more persons)': 'Crowding (7 or more persons)'
    }
    
    print("\n🗺️  Mapping risk factors to sheets:")
    for gbd_rf, sheet_name in risk_factor_mapping.items():
        count = len(gbd_data[gbd_data['risk_factor'] == gbd_rf])
        if sheet_name in prevalence_sheets:
            print(f"   ✅ {gbd_rf} → {sheet_name} ({count} records)")
        else:
            print(f"   ❌ {gbd_rf} → {sheet_name} (sheet not found)")
    
    return risk_factor_mapping

def standardize_country_mapping():
    """Create country name mapping for consistency."""
    return {
        'United States': 'United States of America',
        'Russia': 'Russian Federation',
        'Iran': 'Iran (Islamic Republic of)',
        'South Korea': 'Republic of Korea',
        'North Korea': "Democratic People's Republic of Korea",
        'United Kingdom': 'United Kingdom of Great Britain and Northern Ireland',
        'Venezuela': 'Venezuela (Bolivarian Republic of)',
        'Bolivia': 'Bolivia (Plurinational State of)',
        'Tanzania': 'Tanzania (United Republic of)',
        'Congo': 'Congo',
        'Democratic Republic of the Congo': 'Democratic Republic of the Congo'
    }

def calculate_country_prevalence(country_data, data_source):
    """Calculate prevalence for a country from multiple data points."""
    
    if len(country_data) == 0:
        return None, None, None
    
    # Filter out NaN values
    valid_data = country_data[country_data['value'].notna()]
    
    if len(valid_data) == 0:
        return None, None, None
    
    # For multiple data points, use the most recent or calculate average
    if len(valid_data) == 1:
        prevalence = valid_data['value'].iloc[0]
        ci_lower = valid_data['confidence_interval_lower'].iloc[0]
        ci_upper = valid_data['confidence_interval_upper'].iloc[0]
    else:
        # Use most recent data if available
        if 'year' in valid_data.columns:
            latest_data = valid_data[valid_data['year'] == valid_data['year'].max()]
            if len(latest_data) == 1:
                prevalence = latest_data['value'].iloc[0]
                ci_lower = latest_data['confidence_interval_lower'].iloc[0]
                ci_upper = latest_data['confidence_interval_upper'].iloc[0]
            else:
                # Average of latest year data
                prevalence = latest_data['value'].mean()
                ci_lower = latest_data['confidence_interval_lower'].mean()
                ci_upper = latest_data['confidence_interval_upper'].mean()
        else:
            # Average all available data
            prevalence = valid_data['value'].mean()
            ci_lower = valid_data['confidence_interval_lower'].mean()
            ci_upper = valid_data['confidence_interval_upper'].mean()
    
    return prevalence, ci_lower, ci_upper

def populate_prevalence_sheet(sheet_df, gbd_risk_factor_data, sheet_name):
    """Populate a single prevalence sheet with GBD data."""
    
    print(f"\n📝 Populating {sheet_name}...")
    
    # Get countries from the template
    countries_in_template = sheet_df['Unnamed: 0'].dropna().tolist()
    countries_in_template = [c for c in countries_in_template if c != 'Countries']
    
    print(f"   Template countries: {len(countries_in_template)}")
    
    # Get unique data sources in our GBD data
    data_sources = gbd_risk_factor_data['data_source'].unique()
    print(f"   Available data sources: {data_sources}")
    
    # Create country mapping
    country_mapping = standardize_country_mapping()
    
    # Create new dataframe with populated data
    new_df = sheet_df.copy()
    
    # Track statistics
    populated_cells = 0
    missing_countries = []
    
    # Data source column mapping
    source_col_mapping = {
        'DHS': 'Prevalence (DATA SOURCE HERE)',
        'WHO': 'Prevalence (DATA SOURCE HERE).1', 
        'UNICEF MICS': 'Prevalence (DATA SOURCE HERE).2',
        'WORLD BANK': 'Prevalence (DATA SOURCE HERE).3'
    }
    
    # Populate data for each country
    for idx, country in enumerate(countries_in_template):
        if idx + 1 >= len(new_df):  # Skip if we're beyond the dataframe
            continue
            
        country_found = False
        
        # Try exact match first
        country_data = gbd_risk_factor_data[
            gbd_risk_factor_data['country'].str.contains(country, case=False, na=False)
        ]
        
        # Try mapped country name
        if len(country_data) == 0 and country in country_mapping:
            mapped_country = country_mapping[country]
            country_data = gbd_risk_factor_data[
                gbd_risk_factor_data['country'].str.contains(mapped_country, case=False, na=False)
            ]
        
        if len(country_data) > 0:
            country_found = True
            
            # Populate data for each available source
            for source in data_sources:
                if source in source_col_mapping:
                    col_name = source_col_mapping[source]
                    
                    source_data = country_data[country_data['data_source'] == source]
                    if len(source_data) > 0:
                        prevalence, ci_lower, ci_upper = calculate_country_prevalence(source_data, source)
                        
                        if pd.notna(prevalence):
                            # Format the value with confidence interval if available
                            if pd.notna(ci_lower) and pd.notna(ci_upper):
                                value_str = f"{prevalence:.1f} ({ci_lower:.1f}-{ci_upper:.1f})"
                            else:
                                value_str = f"{prevalence:.1f}"
                            
                            new_df.loc[idx + 1, col_name] = value_str
                            populated_cells += 1
        
        if not country_found:
            missing_countries.append(country)
    
    print(f"   ✅ Populated {populated_cells} cells")
    if missing_countries:
        print(f"   ⚠️  Missing data for {len(missing_countries)} countries")
        print(f"      Examples: {missing_countries[:5]}")
    
    return new_df

def create_populated_master_spreadsheet():
    """Create a new master spreadsheet populated with GBD data."""
    
    print("🎯 === POPULATING MASTER SPREADSHEET WITH GBD DATA ===")
    
    # Load data
    assignment_df, prevalence_sheets = load_master_template()
    gbd_data = load_gbd_data()
    
    # Map risk factors
    risk_factor_mapping = map_risk_factor_sheets(gbd_data, prevalence_sheets)
    
    # Create output file
    output_file = 'GBD_Populated_Master_Spreadsheet.xlsx'
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Copy assignment sheet
        assignment_df.to_excel(writer, sheet_name='Assignment', index=False)
        
        # Populate each prevalence sheet
        for gbd_risk_factor, sheet_name in risk_factor_mapping.items():
            if sheet_name in prevalence_sheets:
                # Get GBD data for this risk factor
                gbd_risk_data = gbd_data[gbd_data['risk_factor'] == gbd_risk_factor]
                
                if len(gbd_risk_data) > 0:
                    # Populate the sheet
                    populated_df = populate_prevalence_sheet(
                        prevalence_sheets[sheet_name], 
                        gbd_risk_data, 
                        sheet_name
                    )
                    
                    # Save to Excel
                    populated_df.to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    # Copy empty template if no data
                    prevalence_sheets[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"\n🎉 Master spreadsheet populated and saved as: {output_file}")
    
    # Create summary report
    create_population_summary(gbd_data, risk_factor_mapping)

def create_population_summary(gbd_data, risk_factor_mapping):
    """Create a summary report of the population process."""
    
    print("\n📊 === POPULATION SUMMARY ===")
    
    summary_data = []
    
    for gbd_risk_factor, sheet_name in risk_factor_mapping.items():
        gbd_risk_data = gbd_data[gbd_data['risk_factor'] == gbd_risk_factor]
        
        if len(gbd_risk_data) > 0:
            summary = {
                'Risk Factor': gbd_risk_factor,
                'Sheet Name': sheet_name,
                'Total Records': len(gbd_risk_data),
                'Countries with Data': gbd_risk_data['country'].nunique(),
                'Data Sources': ', '.join(gbd_risk_data['data_source'].unique()),
                'Year Range': f"{gbd_risk_data['year'].min()}-{gbd_risk_data['year'].max()}" if 'year' in gbd_risk_data.columns else 'N/A',
                'Avg Prevalence': f"{gbd_risk_data['value'].mean():.1f}%" if gbd_risk_data['value'].notna().any() else 'N/A'
            }
        else:
            summary = {
                'Risk Factor': gbd_risk_factor,
                'Sheet Name': sheet_name,
                'Total Records': 0,
                'Countries with Data': 0,
                'Data Sources': 'None',
                'Year Range': 'N/A',
                'Avg Prevalence': 'N/A'
            }
        
        summary_data.append(summary)
    
    summary_df = pd.DataFrame(summary_data)
    
    # Save summary
    summary_df.to_excel('GBD_Population_Summary.xlsx', index=False)
    
    # Print summary
    print(summary_df.to_string(index=False))
    print(f"\n📋 Summary saved as: GBD_Population_Summary.xlsx")

if __name__ == "__main__":
    create_populated_master_spreadsheet() 