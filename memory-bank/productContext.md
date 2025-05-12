# Product Context

*Initial creation.*

**Why this project exists:**

- To automate the process of downloading datasets from various online sources listed in a configuration file.
- To simplify the collection of data needed for further analysis, likely related to Global Burden of Disease (GBD) risk factors.

**Problems it solves:**

- Manual downloading of multiple datasets is time-consuming and error-prone.
- Consolidating data from different sources and formats is challenging.

**How it should work:**

- The tool should read a list of data sources and their URLs from a CSV file.
- It should attempt to download the data from each valid URL.
- Downloaded data should be saved locally in an organized manner.
- The tool should provide feedback on the success or failure of each download attempt.
- (Future) Potentially assist in merging or consolidating the downloaded data.

**User experience goals:**

- Simple execution (run a single script).
- Clear output indicating progress and errors.
- Easy access to the downloaded raw data files. 