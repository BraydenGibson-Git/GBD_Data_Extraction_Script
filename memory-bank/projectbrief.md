# Project Brief

*Initial creation.*

**Core Requirements:**

1.  **Input:** Read data source information (Risk Factor, Assigned To, Data Source name, API/Download Link) from a CSV file (`extracted_data_sources.csv`).
2.  **Processing:** Iterate through the data sources. For each entry with a valid URL, attempt to download the data content.
3.  **Output:** Save each successfully downloaded dataset as a separate file in a designated directory (`downloaded_data`). Files should be named descriptively (e.g., using Risk Factor and Data Source name).
4.  **Error Handling:** Gracefully handle errors such as invalid URLs, network issues, non-existent files, and potentially unsupported data formats.
5.  **Feedback:** Provide console output indicating which URLs are being processed, download success/failure, and where files are saved.

**Goals:**

- Automate the data acquisition process for the specified risk factors.
- Create a repeatable and reliable method for fetching the latest data from the sources.
- Organize the downloaded raw data for subsequent analysis and merging.

**Scope:**

- **In Scope:** Reading CSV, iterating URLs, basic HTTP GET requests, saving raw response content, basic error handling (network, file access), handling common formats like direct CSV/JSON downloads.
- **Out of Scope (Initially):** Complex API authentication, handling formats requiring specific libraries beyond common ones (e.g., SDMX parsers unless simple), data cleaning/transformation, data merging/consolidation logic, graphical user interface. 