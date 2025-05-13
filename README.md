# Data Extractor with Google Sheets Integration

This script extracts data from various API endpoints and URLs, processes JSON responses, and uploads the data directly to Google Sheets. It includes functionality for calculating pooled averages across multiple data sources for the same risk factors.

## Setup

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd <repository_name>
   ```

2. Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up Google Sheets API:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Sheets API
   - Create credentials (OAuth 2.0 Client ID)
   - Download the credentials and save as `credentials.json` in the project directory

5. Prepare your data sources:
   - Create a CSV file named `extracted_data_sources.csv`
   - Include columns: Risk Factor, Assigned To, Data Source, API/Excel Download Link

6. Prepare your Google Sheet:
   - Create a new Google Sheet or use an existing one
   - Get the Spreadsheet ID from the URL:
     `https://docs.google.com/spreadsheets/d/`**spreadsheet_id**`/edit#gid=0`
   - Make sure your Google account has edit access to the sheet

## Specifying the Google Sheet

There are several ways to specify which Google Sheet to use, in order of priority:

1. Command line argument:
   ```bash
   python data_extractor.py --spreadsheet-id your_spreadsheet_id
   ```

2. Environment variable:
   ```bash
   export GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
   python data_extractor.py
   ```

3. Saved configuration:
   - After running the script once, the Spreadsheet ID is saved in `config.json`
   - On subsequent runs, you'll be asked if you want to use the saved ID

4. Interactive input:
   - If no Spreadsheet ID is provided through the above methods
   - The script will guide you through finding and entering the ID

## Usage

1. Run the script:
   ```bash
   python data_extractor.py
   ```

2. Specify the Google Sheet:
   - Command line: `python data_extractor.py --spreadsheet-id your_spreadsheet_id`
   - Environment variable: `export GOOGLE_SPREADSHEET_ID=your_spreadsheet_id`
   - Or enter when prompted

3. The script will:
   - Create individual sheets for each data source
   - Create a "Risk_Factor_Summary" sheet with pooled averages
   - Handle both numeric and non-numeric data appropriately

## Features

- Automatically detects and processes JSON responses
- Converts JSON data into a format suitable for Google Sheets
- Creates separate sheets for each data source
- Handles non-JSON responses by storing them as text
- Provides detailed progress and error reporting
- Saves configuration for easier subsequent runs
- Verifies spreadsheet access before processing

## Output

The script creates two types of sheets:
1. Individual source sheets named: `{risk_factor}_{data_source}`
2. A summary sheet named "Risk_Factor_Summary" containing:
   - Risk Factor name
   - Number of data sources
   - Metrics from all sources
   - Pooled averages (for numeric values)
   - Min/max values
   - Value counts
   - Raw values

## Error Handling

The script includes robust error handling for:
- Network issues
- Invalid URLs
- Authentication problems
- API rate limits
- Invalid JSON responses
- Spreadsheet access issues

## Notes

- The script adds a delay between requests to avoid overwhelming APIs
- Sheet names are truncated to 31 characters (Google Sheets limitation)
- JSON data is processed to create a tabular format suitable for sheets
- Non-JSON responses are stored as plain text in a "Content" column
- Configuration is saved in `config.json` for convenience

## Contributing

1. Create a new branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

3. Push to the repository:
   ```bash
   git push origin feature/your-feature-name
   ```

## Security Notes

- Never commit `credentials.json` or `token.pickle` to the repository
- These files contain sensitive Google API credentials
- They are automatically excluded via .gitignore

## Troubleshooting

- If you get authentication errors, delete `token.pickle` and try again
- If you need to change the Google Sheet, delete `config.json`
- Check the Google Cloud Console if you hit API quotas or limits 