# Global Burden of Disease – Child Health Pipeline

A reproducible pipeline that downloads, cleans and consolidates global child-health risk-factor data, and automatically populates the official **GBD Input-Data Package** template.

## Features

* Fetches indicator data from:
  * **World Bank API**
  * **WHO GHO OData API** (converted from ISO-3 to short country names)
* Pools duplicate sources, derives regional/sub-regional strata from U5 mortality, and imputes missing values.
* Produces three machine-readable outputs plus a fully-populated Excel package:
  * `gbd_processed_data/gbd_consolidated_data.xlsx` – long format
  * `gbd_processed_data/country_list.csv` – definitive country coverage
  * `gbd_processed_data/gbd_input_data_matrix.csv` – tidy wide matrix
  * `GBD_Input_Data_Package.xlsx` – ready for submission

## Quick-start

```bash
# 1. install deps (Python 3.10+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. run the full pipeline (interactive checkpoints disabled)
GBD_PIPELINE_AUTOCONFIRM=1 _SKIP_FINAL_PROMPT_=1 \
python gbd_pipeline_final.py
```

## Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `GBD_PIPELINE_AUTOCONFIRM` | Skip human checkpoints | `0` (off) |
| `_SKIP_FINAL_PROMPT_` | Skip final "press Enter" prompt | `0` |

## Repository layout (post-clean-up)

```
├── gbd_pipeline_final.py          # main orchestrator
├── gbd_enhanced_template_populator.py
├── gbd_processed_data/            # auto-generated outputs
├── memory-bank/                   # persistent project knowledge
├── requirements.txt
└── README.md                      # you are here
```

## Contributing / maintenance

1. Keep the **memory-bank** files up-to-date – they survive memory resets.
2. Use the built-in progress checkpoints for manual QA or pass the env var for CI.
3. After significant analytic or structural changes, regenerate the data package and commit both code + new outputs.

---
© 2025 GBD Child-Health Research Project. MIT License. 