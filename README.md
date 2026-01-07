# 🌍 Global Burden of Disease (GBD) Data Extraction Script

A comprehensive Python pipeline for automatically extracting, processing, and consolidating child health indicators from multiple global data sources.

## 📋 Overview

This project automates the collection of key child health indicators from major international health databases, providing researchers and analysts with clean, standardized datasets for Global Burden of Disease studies.

### 🎯 What This Project Does

- **Fetches data** from multiple APIs: World Bank, WHO (World Health Organization), DHS (Demographic and Health Surveys), and UNICEF
- **Extracts key indicators** including:
  - Child mortality rates (Under-5, Infant, Neonatal)
  - Malnutrition indicators (Stunting, Wasting, Underweight)
  - Birth outcomes (Low birth weight, Birth attendance)
  - Feeding practices (Breastfeeding rates)
  - Population demographics
- **Handles data quality** with automatic cleaning, standardization, and country name normalization
- **Consolidates results** into a single, analysis-ready Excel file
- **Provides regional stratification** based on mortality rates for improved data imputation

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- Internet connection for API access

### Installation

1. **Clone this repository:**
   ```bash
   git clone https://github.com/BraydenGibson-Git/GBD_Data_Extraction_Script.git
   cd GBD_Data_Extraction_Script
   ```

2. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

### Usage

**Option 1: Run the complete pipeline**
```bash
python gbd_pipeline_final.py
```

**Option 2: Follow the interactive tutorial**
Open and run the Jupyter notebook: `tutorial_gbd_data_extraction.ipynb`

## 📚 Tutorial Notebook

The **`tutorial_gbd_data_extraction.ipynb`** is an interactive Jupyter notebook designed for beginners who want to:

- 🎓 **Learn step-by-step** how to fetch data from global health APIs
- 🔍 **Understand the data** structure and quality from each source
- 🛠️ **See the processing** pipeline in action with detailed explanations
- 📊 **Explore the results** with built-in visualizations and summaries
- 🎯 **Customize the approach** for their specific research needs

### What's Included in the Tutorial:

1. **Environment Setup** - Installing packages and importing libraries
2. **API Connections** - Step-by-step connection to each data source
3. **Data Extraction** - Fetching indicators with progress tracking
4. **Data Cleaning** - Standardizing country names and handling missing values
5. **Data Consolidation** - Combining multiple sources intelligently
6. **Export & Visualization** - Saving results and creating summary statistics

The tutorial generates sample outputs in the `tutorial_output/` folder so you can see exactly what the pipeline produces.

## 📁 Project Structure

```
GBD_Data_Extraction_Script/
├── gbd_pipeline_final.py              # Main extraction pipeline
├── gbd_enhanced_template_populator.py # Template population with regional stratification
├── tutorial_gbd_data_extraction.ipynb # Interactive learning notebook
├── requirements.txt                   # Python dependencies
├── tutorial_output/                   # Sample outputs from tutorial
│   ├── gbd_data_package.xlsx         # Consolidated data file
│   └── gbd_summary.csv               # Summary statistics
└── README.md                         # This file
```

## 🔧 Core Features

### Multi-Source Data Integration
- **World Bank API**: Economic and health indicators
- **WHO GHO API**: Global Health Observatory data
- **DHS STATcompiler**: Demographic and Health Survey data
- **UNICEF SDMX**: Population and child-specific indicators

### Advanced Data Processing
- **Smart country matching** using fuzzy matching and standardized country codes
- **Weighted averaging** when multiple sources provide the same indicator
- **Regional stratification** based on child mortality rates (Low/Medium/High)
- **Automatic caching** to avoid redundant API calls
- **Error handling** with retry logic for robust data collection

### Quality Assurance
- **Data validation** checks for completeness and consistency
- **Progress tracking** with detailed logging
- **Flexible configuration** for different indicator sets
- **Export validation** ensuring data integrity

## 📊 Output Data

The pipeline generates:

1. **`gbd_consolidated_data.xlsx`** - Main dataset with all indicators by country and year
2. **`gbd_summary.csv`** - Summary statistics and data coverage report
3. **`country_list.csv`** - Standardized country mappings used
4. **Individual source files** - Raw data from each API for reference

## 🎯 Use Cases

This tool is perfect for:

- **Researchers** studying global child health trends
- **Policy analysts** comparing health outcomes across regions
- **Students** learning about global health data sources
- **NGOs** tracking progress on child health indicators
- **Government agencies** benchmarking national performance

## 📄 License

This project is open source and available under the MIT License.

## 🆘 Support

If you encounter any issues:

1. Check the tutorial notebook for step-by-step guidance
2. Review the error logs generated during execution
3. Open an issue on GitHub with details about your problem

