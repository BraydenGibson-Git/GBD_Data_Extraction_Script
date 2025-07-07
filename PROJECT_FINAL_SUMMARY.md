# GBD Child-Health Data Pipeline – Final Documentation

Date: 8 July 2025 | Version: 3.3 (post-cleanup)

---

## Objective
Provide a single-command, reproducible pipeline that assembles a complete **GBD Input-Data Package** for child health by:
1. Extracting the latest risk-factor indicators from WHO & World Bank APIs.
2. Standardising country names, pooling duplicate sources and imputing gaps via mortality-based strata.
3. Delivering ready-to-use outputs (CSV + Excel) for downstream GBD modelling.

## Data flow
1. **`gbd_pipeline_final.py`** orchestrates extraction ➜ consolidation ➜ tidy transformation ➜ template population.
2. Raw API responses are cached in RAM only – no persisted scrap files post-run.
3. `gbd_enhanced_template_populator.py` handles imputation rules and creates `GBD_Input_Data_Package.xlsx`.
4. Generated files live in `gbd_processed_data/` and project root. All other transient files are auto-cleaned.

## Indicators covered
| Category | Indicator | Source |
|----------|-----------|--------|
| Nutrition | Malnutrition (weight-for-age z<-2) | World Bank |
| Nutrition | Wasting prevalence (U-5) | WHO-GHO |
| Birth | Low birth weight (≤2500 g) | World Bank |
| Feeding | Exclusive breastfeeding <6 months | WHO-GHO |
| Household | Solid fuel use | World Bank |
| Mortality | U5MR | World Bank |
| Population | Population ages 0-4 (absolute) | UNICEF SDMX |

## Imputation hierarchy
1. Latest country-specific value (direct).
2. Mortality-based **sub-regional** average.
3. World-Bank **regional** average.
4. **Global** mean.

## Usage recap
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
GBD_PIPELINE_AUTOCONFIRM=1 python gbd_pipeline_final.py
```
Outputs:
* `gbd_processed_data/gbd_consolidated_data.xlsx` (long)
* `gbd_processed_data/country_list.csv`
* `gbd_processed_data/gbd_input_data_matrix.csv` (wide)
* `GBD_Input_Data_Package.xlsx` – 133 countries, 0 missing risk factors

## Limitations & next steps
* Two micro-states (Cook Islands, Niue) lack population data; integrate UN-DESA pop table for full coverage.
* Add CI to rerun monthly and open PR if any indicator changes.

## Data sources & citations

| Source | Endpoint / Product | Indicators Used | Access Method | Citation |
|--------|--------------------|-----------------|---------------|----------|
| World Bank HNP API | `/country/all/indicator/SH.STA.MALN.ZS` etc. | Malnutrition, Low birth weight, Solid fuel use, Total population, U5MR | `requests` JSON pagination | World Bank. Health Nutrition and Population Statistics. https://data.worldbank.org |
| WHO GHO OData | `https://ghoapi.azureedge.net/api/{code}` | Wasting prevalence, Exclusive breastfeeding | `requests` with OData `$format=json` | World Health Organization. Global Health Observatory. https://www.who.int/data/gho |
| UN IGME (via WB) | Indirectly via WB U5MR series | Under-5 mortality rate (SDG 3.2.1) | Same as WB call above | United Nations Inter-agency Group for Child Mortality Estimation, 2024 |
| UNICEF SDMX API | `https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/UNICEF,DM,1.0/.DM_POP_U5` | Population ages 0-4 (absolute counts) | `requests` (SDMX-JSON) | UNICEF. Demography – Population under age 5. https://data.unicef.org |
| Master template | Provided file `Master Spreadsheet (DO NOT CHANGE YET).xls` | Baseline countries + columns | `xlrd` | --- |

All data were retrieved on **8 July 2025**.

---

## Mortality-based sub-regional stratification (imputation engine)

1. **Source metric:** Latest available Under-5 Mortality Rate (U5MR) for each country (numeric per 1000 live births).
2. **Region of reference:** Countries are first mapped to one of seven World Bank analytical regions using an extended alias dictionary.
3. **Quartile thresholds:** For every WB region, the 25th (Q1) and 75th (Q3) percentiles of U5MR are computed.
4. **Strata assignment:**
   * Low child-mortality = U5MR < Q1
   * Medium child-mortality = Q1 ≤ U5MR ≤ Q3
   * High child-mortality = U5MR > Q3
   The stratum label is concatenated with the region (e.g. `SSA - High Child Mortality`).
5. **Imputation hierarchy:** When a country–indicator value is missing, the pipeline seeks (in order):
   a. A direct country value (latest year).
   b. The sub-regional mean for that indicator.
   c. The WB regional mean.
   d. Global mean.

This approach preserves intra-regional heterogeneity and produces realistic proxy values, especially for risk factors correlated with child survival.

---

**Authors:** Harvey Koh, Brayden Gibson, Stella Talic

© 2025 GBD Child-Health Research Project. MIT License. 