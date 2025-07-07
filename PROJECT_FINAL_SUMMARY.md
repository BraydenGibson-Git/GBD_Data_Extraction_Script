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
| Population | Total & 0-14 population | World Bank |

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

---
**Lead Dev:** Cline (AI-assisted).  Licensed MIT + data-source licenses. 