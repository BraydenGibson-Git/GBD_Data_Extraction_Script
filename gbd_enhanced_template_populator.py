#!/usr/bin/env python3
"""
GBD Template Populator with Sub-Regional Stratification
=========================================================

This script creates a copy of the master spreadsheet and populates it using a
data-driven, sub-regional stratification based on child mortality rates.

Stratification Strategy:
- World Bank Regions are stratified into Low, Medium, and High mortality groups
  based on the 25th and 75th percentiles of Under-5 Mortality Rate (U5MR).
- This provides more accurate regional averages for data imputation.

Author: GBD Research Project
Date: July 2025
Version: 2.0 - Sub-Regional Stratification
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class EnhancedTemplatePopulator:
    """Enhanced template populator with mortality-based sub-regional stratification"""
    
    def __init__(self):
        self.wb_regions = self._get_world_bank_regions()
        self.sub_regional_map = {}
        self.sub_regional_stats = {}
        self.regional_stats = {}

    def _get_world_bank_regions(self):
        """
        World Bank Regional Classifications (2023)
        Source: https://datahelpdesk.worldbank.org/knowledgebase/articles/906519
        
        Regions:
        - SSA: Sub-Saharan Africa (48 countries)
        - MENA: Middle East & North Africa (21 countries) 
        - EAP: East Asia & Pacific (29 countries)
        - SA: South Asia (8 countries)
        - ECA: Europe & Central Asia (49 countries)
        - LAC: Latin America & Caribbean (34 countries)
        - NA: North America (2 countries)
        """
        regions = {
            'SSA': ['Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi', 'Cameroon', 
                    'Cape Verde', 'Central African Republic', 'Chad', 'Comoros', 'Congo, Dem. Rep.', 
                    'Congo, Rep.', 'Cote d\'Ivoire', 'Equatorial Guinea', 'Eritrea', 'Eswatini', 
                    'Ethiopia', 'Gabon', 'Gambia', 'Ghana', 'Guinea', 'Guinea-Bissau', 'Kenya', 
                    'Lesotho', 'Liberia', 'Madagascar', 'Malawi', 'Mali', 'Mauritania', 'Mauritius', 
                    'Mozambique', 'Namibia', 'Niger', 'Nigeria', 'Rwanda', 'Sao Tome and Principe', 
                    'Senegal', 'Seychelles', 'Sierra Leone', 'Somalia', 'South Africa', 'South Sudan', 
                    'Sudan', 'Tanzania', 'Togo', 'Uganda', 'Zambia', 'Zimbabwe'],
            
            'MENA': ['Algeria', 'Bahrain', 'Djibouti', 'Egypt', 'Iran', 'Iraq', 'Israel', 'Jordan', 
                     'Kuwait', 'Lebanon', 'Libya', 'Malta', 'Morocco', 'Oman', 'Qatar', 'Saudi Arabia', 
                     'Syria', 'Tunisia', 'United Arab Emirates', 'West Bank and Gaza', 'Yemen'],
            
            'EAP': ['Australia', 'Brunei', 'Cambodia', 'China', 'Fiji', 'Indonesia', 'Japan', 
                    'Kiribati', 'Korea, Rep.', 'Lao PDR', 'Malaysia', 'Marshall Islands', 'Micronesia', 
                    'Mongolia', 'Myanmar', 'Nauru', 'New Zealand', 'Palau', 'Papua New Guinea', 
                    'Philippines', 'Samoa', 'Singapore', 'Solomon Islands', 'Thailand', 'Timor-Leste', 
                    'Tonga', 'Tuvalu', 'Vanuatu', 'Vietnam'],
            
            'SA': ['Afghanistan', 'Bangladesh', 'Bhutan', 'India', 'Maldives', 'Nepal', 'Pakistan', 'Sri Lanka'],
            
            'ECA': ['Albania', 'Armenia', 'Austria', 'Azerbaijan', 'Belarus', 'Belgium', 'Bosnia and Herzegovina', 
                    'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic', 'Denmark', 'Estonia', 'Finland', 
                    'France', 'Georgia', 'Germany', 'Greece', 'Hungary', 'Iceland', 'Ireland', 'Italy', 
                    'Kazakhstan', 'Kosovo', 'Kyrgyz Republic', 'Latvia', 'Lithuania', 'Luxembourg', 
                    'Moldova', 'Montenegro', 'Netherlands', 'North Macedonia', 'Norway', 'Poland', 
                    'Portugal', 'Romania', 'Russian Federation', 'Serbia', 'Slovak Republic', 'Slovenia', 
                    'Spain', 'Sweden', 'Switzerland', 'Tajikistan', 'Turkey', 'Turkmenistan', 'Ukraine', 
                    'United Kingdom', 'Uzbekistan'],
            
            'LAC': ['Antigua and Barbuda', 'Argentina', 'Bahamas', 'Barbados', 'Belize', 'Bolivia', 'Brazil', 
                    'Chile', 'Colombia', 'Costa Rica', 'Cuba', 'Dominica', 'Dominican Republic', 'Ecuador', 
                    'El Salvador', 'Grenada', 'Guatemala', 'Guyana', 'Haiti', 'Honduras', 'Jamaica', 
                    'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Puerto Rico', 'St. Kitts and Nevis', 
                    'St. Lucia', 'St. Vincent and the Grenadines', 'Suriname', 'Trinidad and Tobago', 
                    'Uruguay', 'Venezuela'],
            
            'NA': ['Canada', 'United States']
        }
        
        # Create reverse mapping with alternative names
        country_to_region = {}
        for region, countries in regions.items():
            for country in countries:
                country_to_region[country] = region
                
        # Add alternative country names for better matching
        alternatives = {
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
            'Tanzania': ['United Republic of Tanzania'],
            'Eswatini': ['Swaziland'],
            'Timor-Leste': ['Timor Leste']
        }
        
        for main_name, alt_names in alternatives.items():
            if main_name in country_to_region:
                region = country_to_region[main_name]
                for alt_name in alt_names:
                    country_to_region[alt_name] = region
                    
        return country_to_region
    
    def _generate_sub_regional_classification(self, gbd_data):
        """
        Generates a sub-regional classification based on U5MR quartiles.
        This method populates self.sub_regional_map.
        """
        print("🧬 Generating sub-regional strata based on child mortality...")
        
        mortality_df = gbd_data[gbd_data['risk_factor'] == 'Child Mortality Rate (U5MR)'].copy()
        
        # Add main World Bank region
        mortality_df['region'] = mortality_df['country'].map(self.wb_regions)
        mortality_df.dropna(subset=['region'], inplace=True)
        
        # Get the most recent mortality rate for each country
        latest_mortality = mortality_df.sort_values('year', ascending=False).drop_duplicates('country')
        
        # Calculate quartile thresholds for each region
        regional_thresholds = latest_mortality.groupby('region')['value'].describe(percentiles=[.25, .75])
        
        sub_regional_map = {}
        for idx, country_row in latest_mortality.iterrows():
            country = country_row['country']
            region = country_row['region']
            u5mr = country_row['value']
            
            if region in regional_thresholds.index:
                q1 = regional_thresholds.loc[region, '25%']
                q3 = regional_thresholds.loc[region, '75%']
                
                stratum = 'Medium'
                if u5mr < q1:
                    stratum = 'Low'
                elif u5mr > q3:
                    stratum = 'High'
                
                sub_regional_map[country] = f"{region}_{stratum}"
        
        self.sub_regional_map = sub_regional_map
        print(f"   ✅ Classified {len(sub_regional_map)} countries into sub-regions.")
        return sub_regional_map

    def _calculate_imputation_averages(self, gbd_data):
        """Calculate regional and sub-regional averages for imputation."""
        print("🧮 Calculating imputation averages for regions and sub-regions...")
        
        # Add region and sub-region columns to the data
        gbd_with_regions = gbd_data.copy()
        gbd_with_regions['region'] = gbd_with_regions['country'].map(self.wb_regions)
        gbd_with_regions['sub_region'] = gbd_with_regions['country'].map(self.sub_regional_map)
        
        risk_factors = gbd_data['risk_factor'].unique()
        
        for risk_factor in risk_factors:
            risk_data = gbd_with_regions[gbd_with_regions['risk_factor'] == risk_factor]
            
            # Calculate main regional averages (as a fallback)
            regional_avg = risk_data.groupby('region')['value'].agg(['mean', 'std', 'count']).round(2)
            self.regional_stats[risk_factor] = regional_avg
            
            # Calculate sub-regional averages
            sub_regional_avg = risk_data.groupby('sub_region')['value'].agg(['mean', 'std', 'count']).round(2)
            self.sub_regional_stats[risk_factor] = sub_regional_avg

    def _get_imputation_value(self, country_name, risk_factor, gbd_data):
        """Get value using direct match, sub-regional, or regional imputation."""
        # 1. Direct country match
        direct_match = gbd_data[(gbd_data['risk_factor'] == risk_factor) & (gbd_data['country'] == country_name)]
        if not direct_match.empty:
            latest = direct_match.loc[direct_match['year'].idxmax()]
            return {'value': round(latest['value'], 1), 'method': 'Direct', 'source': latest['source']}
            
        # 2. Sub-regional imputation
        sub_region = self.sub_regional_map.get(country_name)
        if sub_region and risk_factor in self.sub_regional_stats and sub_region in self.sub_regional_stats[risk_factor].index:
            stats = self.sub_regional_stats[risk_factor].loc[sub_region]
            return {'value': round(stats['mean'], 1), 'method': f'Impute_{sub_region}', 'source': f'Avg_n{int(stats["count"])}'}
            
        # 3. Main regional imputation (fallback)
        main_region = self.wb_regions.get(country_name)
        if main_region and risk_factor in self.regional_stats and main_region in self.regional_stats[risk_factor].index:
            stats = self.regional_stats[risk_factor].loc[main_region]
            return {'value': round(stats['mean'], 1), 'method': f'Impute_{main_region}', 'source': f'Avg_n{int(stats["count"])}'}
        
        return None

    def create_populated_template(self, template_file, gbd_data_file=None):
        """Create a populated copy of the master template with sub-regional stratification."""
        print("🎯 === TEMPLATE POPULATION WITH SUB-REGIONAL STRATIFICATION ===")
        print(f"Started: {datetime.now()}")
        
        print(f"📊 Loading GBD data from: {gbd_data_file}")
        gbd_data = pd.read_excel(gbd_data_file, sheet_name='All_Data')
        
        self._generate_sub_regional_classification(gbd_data)
        self._calculate_imputation_averages(gbd_data)
        
        print(f"📋 Loading template: {template_file}")
        df = pd.read_excel(template_file, sheet_name='ESTIMATES 2010-11')
        new_df = df.copy()
        
        risk_factor_mapping = {
            'Malnutrition (wght-for-age z<-2)': 3, 'Low birth weight (=<2500 g)': 4,
            'Non-breastfed exclus. (4 mths)': 5, 'Use solid fuels (yes)': 6,
            'Crowding (5 or more persons)': 7, 'Child Mortality Rate (U5MR)': 8
        }
        
        update_log = []
        print("\n🔄 Processing countries...")
        
        for i in range(16, len(new_df)):
            country_name = new_df.iloc[i, 0]
            if pd.isna(country_name) or not isinstance(country_name, str) or len(country_name.strip()) < 2:
                continue
            if any(skip in country_name.lower() for skip in ['risk', 'comparison', 'population', 'incidence']):
                continue
                
            sub_region = self.sub_regional_map.get(country_name, self.wb_regions.get(country_name, 'Unknown'))
            print(f"   🌍 Processing: {country_name} ({sub_region})")
            
            new_df.iloc[i, 2] = sub_region
            
            for gbd_risk_factor, col_idx in risk_factor_mapping.items():
                result = self._get_imputation_value(country_name, gbd_risk_factor, gbd_data)
                if result:
                    update_log.append({'Country': country_name, 'Sub_Region': sub_region, 'Risk_Factor': gbd_risk_factor, 
                                       'Old_Value': new_df.iloc[i, col_idx], 'New_Value': result['value'], 
                                       'Method': result['method'], 'Source': result['source']})
                    new_df.iloc[i, col_idx] = result['value']
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = f'GBD_Stratified_Template_{timestamp}.xlsx'
        
        print(f"\n💾 Saving stratified template to {output_file}...")
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            new_df.to_excel(writer, sheet_name='ESTIMATES_Stratified', index=False)
            pd.DataFrame(update_log).to_excel(writer, sheet_name='Update_Log', index=False)
            
            # Save the sub-regional stats for reference
            stats_to_save = []
            for rf, data in self.sub_regional_stats.items():
                data = data.reset_index()
                data['risk_factor'] = rf
                stats_to_save.append(data)
            pd.concat(stats_to_save).to_excel(writer, sheet_name='Sub_Regional_Averages', index=False)
        
        print(f"\n🎉 Stratified template creation completed: {datetime.now()}")
        return output_file

def main():
    """Main function to run the populator."""
    template_file = 'Master Spreadsheet (DO NOT CHANGE YET).xls'
    gbd_data_file = 'gbd_processed_data/gbd_final_with_mortality.xlsx'
    
    if not os.path.exists(template_file) or not os.path.exists(gbd_data_file):
        print("❌ Required file not found. Please ensure both master template and GBD data file exist.")
        print("Run `python gbd_child_mortality_pipeline.py` first.")
        return
        
    populator = EnhancedTemplatePopulator()
    output_file = populator.create_populated_template(template_file, gbd_data_file)
    
    if output_file:
        print(f"\n✅ Success! Stratified template created: {output_file}")

if __name__ == "__main__":
    main() 