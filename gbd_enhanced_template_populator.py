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
Version: 2.1 - Country Normalization Fix
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
import warnings
import country_converter as coco
import logging, contextlib, io

# Silence country_converter's verbose print/log output
logging.getLogger('country_converter').setLevel(logging.ERROR)

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

class EnhancedTemplatePopulator:
    """Enhanced template populator with mortality-based sub-regional stratification"""
    
    def __init__(self):
        self.country_to_region = self._get_world_bank_regions()
        self.sub_regional_map = {}
        self.sub_regional_stats = {}
        self.regional_stats = {}
        self.global_averages = {}

    def _get_world_bank_regions(self):
        """
        World Bank Regional Classifications (2023)
        Source: https://datahelpdesk.worldbank.org/knowledgebase/articles/906519
        
        Returns a dictionary mapping country names (and alternatives) to their region.
        """
        regions = {
            'SSA': ['Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi', 'Cameroon', 'Cape Verde', 'Central African Republic', 'Chad', 'Comoros', 'Congo, Dem. Rep.', 'Congo, Rep.', 'Cote d\'Ivoire', 'Equatorial Guinea', 'Eritrea', 'Eswatini', 'Ethiopia', 'Gabon', 'Gambia', 'Ghana', 'Guinea', 'Guinea-Bissau', 'Kenya', 'Lesotho', 'Liberia', 'Madagascar', 'Malawi', 'Mali', 'Mauritania', 'Mauritius', 'Mozambique', 'Namibia', 'Niger', 'Nigeria', 'Rwanda', 'Sao Tome and Principe', 'Senegal', 'Seychelles', 'Sierra Leone', 'Somalia', 'South Africa', 'South Sudan', 'Sudan', 'Tanzania', 'Togo', 'Uganda', 'Zambia', 'Zimbabwe'],
            'MENA': ['Algeria', 'Bahrain', 'Djibouti', 'Egypt', 'Iran', 'Iraq', 'Israel', 'Jordan', 'Kuwait', 'Lebanon', 'Libya', 'Malta', 'Morocco', 'Oman', 'Qatar', 'Saudi Arabia', 'Syria', 'Tunisia', 'United Arab Emirates', 'West Bank and Gaza', 'Yemen'],
            'EAP': ['Australia', 'Brunei', 'Cambodia', 'China', 'Fiji', 'Indonesia', 'Japan', 'Kiribati', 'Korea, Rep.', 'Lao PDR', 'Malaysia', 'Marshall Islands', 'Micronesia', 'Mongolia', 'Myanmar', 'Nauru', 'New Zealand', 'Palau', 'Papua New Guinea', 'Philippines', 'Samoa', 'Singapore', 'Solomon Islands', 'Thailand', 'Timor-Leste', 'Tonga', 'Tuvalu', 'Vanuatu', 'Vietnam'],
            'SA': ['Afghanistan', 'Bangladesh', 'Bhutan', 'India', 'Maldives', 'Nepal', 'Pakistan', 'Sri Lanka'],
            'ECA': ['Albania', 'Armenia', 'Austria', 'Azerbaijan', 'Belarus', 'Belgium', 'Bosnia and Herzegovina', 'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic', 'Denmark', 'Estonia', 'Finland', 'France', 'Georgia', 'Germany', 'Greece', 'Hungary', 'Iceland', 'Ireland', 'Italy', 'Kazakhstan', 'Kosovo', 'Kyrgyz Republic', 'Latvia', 'Lithuania', 'Luxembourg', 'Moldova', 'Montenegro', 'Netherlands', 'North Macedonia', 'Norway', 'Poland', 'Portugal', 'Romania', 'Russian Federation', 'Serbia', 'Slovak Republic', 'Slovenia', 'Spain', 'Sweden', 'Switzerland', 'Tajikistan', 'Turkey', 'Turkmenistan', 'Ukraine', 'United Kingdom', 'Uzbekistan'],
            'LAC': ['Antigua and Barbuda', 'Argentina', 'Bahamas', 'Barbados', 'Belize', 'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Costa Rica', 'Cuba', 'Dominica', 'Dominican Republic', 'Ecuador', 'El Salvador', 'Grenada', 'Guatemala', 'Guyana', 'Haiti', 'Honduras', 'Jamaica', 'Mexico', 'Nicaragua', 'Panama', 'Paraguay', 'Peru', 'Puerto Rico', 'St. Kitts and Nevis', 'St. Lucia', 'St. Vincent and the Grenadines', 'Suriname', 'Trinidad and Tobago', 'Uruguay', 'Venezuela'],
            'NA': ['Canada', 'United States']
        }
        
        country_to_region = {}
        for region, countries in regions.items():
            for country in countries:
                country_to_region[country] = region
                
        alternatives = {
            'Congo, Dem. Rep.': ['Democratic Republic of the Congo', 'Congo DRC', 'DRC', 'Dem. Rep. of the Congo'], 'Congo, Rep.': ['Congo', 'Republic of the Congo'], 'Cote d\'Ivoire': ['Ivory Coast', 'Côte d\'Ivoire'], 'Iran': ['Iran (Islamic Republic of)'], 'Korea, Rep.': ['South Korea', 'Republic of Korea'], 'Lao PDR': ['Laos', 'Lao People\'s Dem. Republic'], 'Russian Federation': ['Russia'], 'United States': ['United States of America', 'USA'], 'United Kingdom': ['UK'], 'Vietnam': ['Viet Nam'], 'Syria': ['Syrian Arab Republic'], 'Libya': ['Libyan Arab Jamahiriya'], 'Tanzania': ['United Republic of Tanzania'], 'Eswatini': ['Swaziland'], 'Timor-Leste': ['Timor Leste']
        }
        
        for main_name, alt_names in alternatives.items():
            if main_name in country_to_region:
                region = country_to_region[main_name]
                for alt_name in alt_names:
                    country_to_region[alt_name] = region
                    
        return country_to_region

    def _normalize_country_names(self, df, country_col='country'):
        """Standardizes country names to a consistent format using country_converter."""
        print(f"   🤖 Normalizing country names in column '{country_col}'...")
        # Use country_converter in a silenced context to suppress noisy stdout/stderr.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df[country_col] = coco.convert(names=df[country_col].tolist(), to='name_short', not_found=np.nan)
        
        # --- BRUTE FORCE FIX: Ensure no lists remain in the country column ---
        df[country_col] = df[country_col].apply(lambda x: x[0] if isinstance(x, list) else x)
        
        # Drop rows where a country name could not be found (i.e., regional aggregates)
        original_count = len(df)
        df.dropna(subset=[country_col], inplace=True)
        new_count = len(df)
        if original_count > new_count:
            print(f"      🗑️ Dropped {original_count - new_count} rows with non-standard country names.")
        print("      ✅ Normalization complete.")
        return df

    def _generate_sub_regional_classification(self, gbd_data):
        """Generates sub-regional classifications using the long-format data."""
        print("🧬 Generating sub-regional strata based on child mortality...")
        mortality_df = gbd_data[gbd_data['risk_factor'] == 'Child Mortality Rate (U5MR)'].copy()
        if mortality_df.empty:
            print("   ⚠️ No U5MR data found. Skipping sub-regional classification.")
            return
            
        latest_mortality = mortality_df.sort_values('year', ascending=False).drop_duplicates('country')
        latest_mortality['wb_region'] = latest_mortality['country'].map(self.country_to_region)
        
        regional_quartiles = latest_mortality.groupby('wb_region')['value'].quantile([0.25, 0.75]).unstack()
        
        self.sub_regional_map = {}
        for _, row in latest_mortality.iterrows():
            country, region, u5mr = row['country'], row['wb_region'], row['value']
            if pd.notna(region) and region in regional_quartiles.index:
                q1, q3 = regional_quartiles.loc[region, 0.25], regional_quartiles.loc[region, 0.75]
                classification = 'Medium' if q1 <= u5mr <= q3 else ('Low' if u5mr < q1 else 'High')
                self.sub_regional_map[country] = f"{region} - {classification} Child Mortality"
        print(f"   ✅ Classified {len(self.sub_regional_map)} countries.")

    def _calculate_imputation_averages(self, gbd_data):
        """Calculates imputation averages from the long-format data."""
        print("🧮 Calculating imputation averages...")
        gbd_data['wb_region'] = gbd_data['country'].map(self.country_to_region)
        gbd_data['sub_region'] = gbd_data['country'].map(self.sub_regional_map)
        
        self.global_averages = gbd_data.groupby('risk_factor')['value'].mean()
        self.regional_stats = gbd_data.groupby(['wb_region', 'risk_factor'])['value'].mean()
        self.sub_regional_stats = gbd_data.groupby(['sub_region', 'risk_factor'])['value'].mean()
        print("   ✅ Averages calculated for all levels.")

    def _get_imputation_value(self, country, risk_factor, gbd_data):
        """Gets a value from long-format data, using a robust fallback system."""
        # Find the latest direct match for the country and risk factor
        direct_match = gbd_data[(gbd_data['country'] == country) & (gbd_data['risk_factor'] == risk_factor)]
        if not direct_match.empty:
            latest = direct_match.sort_values('year', ascending=False).iloc[0]
            return {'value': latest['value'], 'method': 'Direct', 'source': f"{latest['source']} ({latest['year']})"}
        
        # Fallback 1: Sub-regional average
        sub_region = self.sub_regional_map.get(country)
        if sub_region and (sub_region, risk_factor) in self.sub_regional_stats:
            val = self.sub_regional_stats.loc[(sub_region, risk_factor)]
            return {'value': val, 'method': f'Imputed ({sub_region})', 'source': 'Calculated Average'}
            
        # Fallback 2: Regional average
        region = self.country_to_region.get(country)
        if region and (region, risk_factor) in self.regional_stats:
            val = self.regional_stats.loc[(region, risk_factor)]
            return {'value': val, 'method': f'Imputed (Region: {region})', 'source': 'Calculated Average'}
            
        # Fallback 3: Global average
        if risk_factor in self.global_averages:
            val = self.global_averages.loc[risk_factor]
            return {'value': val, 'method': 'Imputed (Global)', 'source': 'Calculated Average'}
        return None

    def create_populated_template(self, template_file, gbd_data_file=None):
        """Creates a data package from long-format GBD data."""
        print("\n🎯 === DATA PACKAGE CREATION (ROBUST LONG-FORMAT METHOD) ===")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"   📂 Reading data from {gbd_data_file}...")
        gbd_data = pd.read_excel(gbd_data_file, sheet_name='RiskFactors_Mortality')
        population_df = pd.read_excel(gbd_data_file, sheet_name='Under14_Population')
        
        # --- Normalize all country names at the beginning ---
        gbd_data = self._normalize_country_names(gbd_data, 'country')
        population_df = self._normalize_country_names(population_df, 'country')

        self._generate_sub_regional_classification(gbd_data)
        self._calculate_imputation_averages(gbd_data)
        
        print("\n📝 Reading and preparing master template...")
        master_df = pd.read_excel(template_file, sheet_name='ESTIMATES 2010-11', engine='xlrd')
        master_df.rename(columns={master_df.columns[0]: 'Country'}, inplace=True)
        master_df = self._normalize_country_names(master_df, 'Country')

        pop_dict = population_df.set_index('country')['under_14_population'].to_dict()

        risk_factor_mapping = {
            'Malnutrition (wght-for-age z<-2)': 'Malnutrition',
            'Wasting prevalence among children under 5 years': 'Wasting',
            'Low birth weight (=<2500 g)': 'Low_Birth_Weight',
            'Exclusive breastfeeding under 6 months (%)': 'Exclusive_Breastfeeding',
            'Use solid fuels (yes)': 'Solid_Fuels',
            'Child Mortality Rate (U5MR)': 'U5MR'
        }
        
        print(f"    Population data ready for {len(pop_dict)} countries.")
        print(f"   Processing {len(master_df)} countries from the template...")

        input_data_rows, update_log = [], []
        for index, row in master_df.iterrows():
            country_name = row['Country']
            if pd.isna(country_name) or len(str(country_name).strip()) < 2:
                continue

            sub_region = self.sub_regional_map.get(country_name, self.country_to_region.get(country_name, 'Unknown'))
            
            original_pop = row.get('U5_Population', np.nan) 
            new_pop = pop_dict.get(country_name, original_pop)

            row_data = {'Country': country_name, 'Sub_Region': sub_region, 'Population_0_14': new_pop}
            
            for gbd_risk_factor, clean_name in risk_factor_mapping.items():
                result = self._get_imputation_value(country_name, gbd_risk_factor, gbd_data)
                if result:
                    row_data[clean_name] = result['value']
                    update_log.append({'Country': country_name, 'Indicator': clean_name, 'New_Value': result['value'], 'Method': result['method'], 'Source': result['source']})
            input_data_rows.append(row_data)

        input_df = pd.DataFrame(input_data_rows)

        # ------------------------------------------------------------------
        # FINAL CLEAN-UP: drop rows with no numeric data & purge NaNs
        # ------------------------------------------------------------------
        value_cols = [v for v in risk_factor_mapping.values()]
        before_rows = len(input_df)
        input_df = input_df.dropna(subset=value_cols, how='all')
        after_rows = len(input_df)
        if before_rows != after_rows:
            print(f"   🗑️ Removed {before_rows - after_rows} template rows without any numeric values.")

        # Replace remaining NaNs with blanks for cleaner Excel display
        input_df[value_cols] = input_df[value_cols].fillna('')

        print(f"   ✅ Processed {len(input_df)} countries into final format (no NaNs).")

        output_file = 'GBD_Input_Data_Package.xlsx'
        print(f"\n💾 Creating new data package workbook '{output_file}'…")

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            input_df.to_excel(writer, sheet_name='GBD_INPUT_DATA', index=False)
            pd.DataFrame(update_log).to_excel(writer, sheet_name='Update_Log', index=False)

        print(f"🎉 New data package created successfully: {output_file}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return output_file

def main():
    """Main function to run the populator"""
    populator = EnhancedTemplatePopulator()
    # This script is designed to be called by the main pipeline
    # For standalone testing, you can uncomment and adjust the lines below.
    # populator.create_populated_template(
    #     template_file='Master Spreadsheet (DO NOT CHANGE YET).xls',
    #     gbd_data_file='gbd_processed_data/gbd_final_with_mortality_and_pop.xlsx'
    # )

if __name__ == '__main__':
    main() 