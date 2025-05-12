# System Patterns

*Initial creation.*

**System Architecture:**

- Single script (`data_extractor.py`) performing data extraction.
- Reads configuration/input from a CSV file (`extracted_data_sources.csv`).
- Fetches data from external web URLs/APIs.
- Stores downloaded data locally in a designated folder (`downloaded_data`).

**Key Technical Decisions:**

- Use Python for scripting due to its strong data handling libraries.
- Use `pandas` for reading and manipulating the input CSV.
- Use a dedicated directory for downloaded data to maintain organization.

**Design Patterns in Use:**

- Configuration-driven processing (script behavior determined by input CSV).
- Modular functions (e.g., `read_data_sources`, planned download function).

**Component Relationships:**

- `data_extractor.py` depends on `extracted_data_sources.csv`.
- `data_extractor.py` writes to the `downloaded_data/` directory.

**Critical Implementation Paths:**

- Robust handling of network requests and potential errors.
- Parsing/saving logic for different data formats (CSV, JSON, etc.). 