# GBD Data Processing Pipeline: Final Project Summary

## 1. Project Overview

This project successfully developed an automated data processing pipeline to support Global Burden of Disease (GBD) analysis. The primary goal was to create a robust, local system to replace a manual Google Sheets workflow. The final pipeline automatically extracts data from multiple international health organizations, processes it into a standardized format, and populates a sophisticated research template with the latest available data, including mortality-stratified regional imputations for missing values.

The key achievements include:
- **Full Automation:** Replaced manual data gathering with an automated pipeline.
- **Data Consolidation:** Integrated data from 5 major risk factors and child mortality from multiple sources.
- **Advanced Imputation:** Developed a data-driven, sub-regional stratification model based on child mortality rates to provide highly accurate imputations for missing data.
- **Comprehensive Output:** Generated a final, populated research spreadsheet with full logging and transparency.

---

## 2. Data Sources & Citations

The pipeline integrates data from the following official sources:

*   **UNICEF MICS (Statistical Data Warehouse)**
    *   **Indicators:** Malnutrition, Household Crowding
    *   **Citation:** UNICEF. (2025). *Statistical Data Warehouse. Multiple Indicator Cluster Surveys (MICS)*. Retrieved from https://data.unicef.org/

*   **DHS Program (Demographic and Health Surveys)**
    *   **Indicators:** Malnutrition, Low Birth Weight, Non-Breastfeeding, Solid Fuel Use, Crowding
    *   **Citation:** DHS Program. (2025). *Demographic and Health Surveys Data API*. Retrieved from https://api.dhsprogram.com/

*   **World Health Organization (WHO) - Global Health Observatory (GHO)**
    *   **Indicators:** Malnutrition, Low Birth Weight
    *   **Citation:** World Health Organization. (2025). *Global Health Observatory Data Repository*. Retrieved from https://www.who.int/data/gho

*   **World Bank - Health Nutrition and Population Statistics**
    *   **Indicators:** Malnutrition, Low Birth Weight
    *   **Citation:** World Bank. (2025). *Health Nutrition and Population Statistics*. Retrieved from https://data.worldbank.org/

*   **WHO GHO - Under-Five Mortality Rate (U5MR)**
    *   **Indicator:** Under-five mortality rate (per 1000 live births) - SDG 3.2.1
    *   **Citation:** UN Inter-agency Group for Child Mortality Estimation (UN IGME). (2024). *Levels & Trends in Child Mortality Report*. Retrieved from WHO Global Health Observatory, https://www.who.int/data/gho/data/indicators/indicator-details/GHO/under-five-mortality-rate-(per-1000-live-births)

*   **Population & Regional Classifications**
    *   **Population:** United Nations, Department of Economic and Social Affairs, Population Division. (2022). *World Population Prospects 2022*. Retrieved from https://population.un.org/wpp/
    *   **Regions:** World Bank. (2023). *World Bank Country and Lending Groups*. Retrieved from https://datahelpdesk.worldbank.org/knowledgebase/articles/906519

---

## 3. Methodology: Sub-Regional Classification

To achieve the highest possible accuracy for data imputation, we developed a data-driven sub-regional classification system. This moves beyond broad regional averages to a more granular, analytically sound model.

### 3.1. The Framework

The system is built on a two-tier classification:

1.  **Tier 1: World Bank Regions:** We first classify all countries into one of the seven standard World Bank analytical regions (e.g., Sub-Saharan Africa, South Asia, etc.).
2.  **Tier 2: Mortality-Based Strata:** We then subdivide each World Bank region into three **strata** based on their most recently reported **Under-Five Mortality Rate (U5MR)**.

### 3.2. The Stratification Process

The stratification is performed dynamically every time the pipeline is run:

1.  **Analyze U5MR Distribution:** The script calculates the statistical distribution of U5MR for all countries within a given World Bank region.
2.  **Define Quartile Thresholds:** It identifies the **25th percentile (Q1)** and the **75th percentile (Q3)** for the mortality rates in that region.
3.  **Assign Strata:** Each country is then assigned to a stratum:
    *   **Low Mortality:** U5MR is below the 25th percentile.
    *   **Medium Mortality:** U5MR is between the 25th and 75th percentile.
    *   **High Mortality:** U5MR is above the 75th percentile.

This results in a much more specific classification, such as `SSA_Low`, `SSA_Medium`, or `SA_High`.

### 3.3. Impact on Imputation

When data for a specific risk factor is missing for a country, the pipeline uses the average value from its specific **sub-regional stratum**. For example, if malnutrition data is missing for a country classified as `SSA_High`, the pipeline will impute the average malnutrition value calculated *only* from other `SSA_High` countries. This is significantly more accurate than using a broad average from all of Sub-Saharan Africa.

This methodology ensures that our imputations are as precise and contextually relevant as possible, respecting the epidemiological similarities between countries with comparable child mortality outcomes. 