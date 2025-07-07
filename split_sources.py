import pandas as pd
import os

def split_data_by_source():
    """
    Reads the consolidated GBD data file and splits it into separate
    CSV files for each unique data source.
    """
    
    print("Splitting consolidated data file into individual sources...")
    
    # Define input file and output directory
    input_file = 'gbd_processed_data/gbd_final_with_mortality.xlsx'
    output_dir = 'final_data_sources'
    
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
        
    # Check if the input file exists
    if not os.path.exists(input_file):
        print(f"ERROR: Input file not found at '{input_file}'")
        print("Please run the main child mortality pipeline first.")
        return
        
    # Load the consolidated data
    df = pd.read_excel(input_file, sheet_name='All_Data')
    
    # Get unique sources from the 'source' column
    unique_sources = df['source'].unique()
    
    print(f"Found {len(unique_sources)} unique sources: {', '.join(unique_sources)}")
    
    # For each source, filter data and save to a new CSV
    for source in unique_sources:
        print(f"  - Processing source: {source}")
        source_df = df[df['source'] == source]
        
        # Define a clean filename
        output_filename = f"{source}_data.csv"
        output_path = os.path.join(output_dir, output_filename)
        
        # Save to CSV
        source_df.to_csv(output_path, index=False)
        print(f"    -> Saved {len(source_df)} records to {output_path}")
        
    print("\nSuccessfully split all data sources into individual files.")

if __name__ == "__main__":
    split_data_by_source() 