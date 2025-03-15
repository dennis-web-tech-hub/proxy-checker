<div align="center">
   <img src="src/img/icon.png" alt="ProxyChecker" width="200" height="200"> 
   <h1>ProxyChecker</h1> 
   <p>A concurrent and efficient proxy checker for testing HTTP, SOCKS4, and SOCKS5 proxies with a modern, GUI-based interface.</p> 
   <a href="#features"><strong>Features</strong></a> •
   <a href="#installation"><strong>Installation</strong></a> •
   <a href="#usage"><strong>Usage</strong></a> •
   <a href="#configuration"><strong>Configuration</strong></a> •
   <a href="#troubleshooting"><strong>Troubleshooting</strong></a> •
   <a href="#contributing"><strong>Contributing</strong></a>
</div>

---

# Overview

**ProxyChecker** is a Python tool designed to verify the functionality of proxy lists (HTTP, SOCKS4, and SOCKS5) by sending test requests. It supports concurrent testing via multi-threading, provides detailed results including response times, anonymity classification, and geo-location lookup, and saves working proxies in various formats. The application is entirely GUI-based using PyQt6 and now includes several new features to improve usability and control.

# Features

- **Multi-threaded Proxy Checking:**  
  Uses Python’s `ThreadPoolExecutor` to check multiple proxies concurrently.

- **Configurable Timeout and Retries:**  
  Customize the timeout, number of retries, and delay between retries.

- **Supports HTTP, SOCKS4, and SOCKS5 Proxies:**  
  Fetch proxy lists from configurable URLs.

- **Detailed Proxy Analysis:**  
  When enabled, detailed mode provides:
  - **Response Times:** Measures how long each proxy takes to respond.
  - **Anonymity Detection:** Determines whether a proxy is transparent or anonymous.
  - **Geo-Location Lookup:** Retrieves country, region, and city details for working proxies.

- **Multiple Export Formats:**  
  Save working proxy results as plain text (TXT), CSV, or JSON.

- **GUI Application:**  
  An intuitive interface featuring progress bars, log output, and settings dialogs.

- **Automatic Update Checker:**  
  Checks for the latest release at startup and informs you if an update is available.

- **New Features:**
  - **Pause/Resume Functionality:**  
    Temporarily suspend and resume the proxy-checking process.
  - **Custom User-Agent Option:**  
    Provide a custom User-Agent header for HTTP requests.
  - **History Logging:**  
    Appends summary statistics from each run to a `history.log` file.
  - **Filtering Detailed Results:**  
    When in detailed mode, filter working proxies by maximum response time in the results dialog.

# Installation

### Prerequisites

- Python 3.6 or later
- `requests` package for HTTP requests
- `PyQt6` package for the graphical user interface

### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/Jesewe/proxy-checker.git
   cd proxy-checker
   ```
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

# Usage

### Launching the Application

Simply run the following command to start the GUI:
```bash
python proxy-checker.py
```
Once launched, configure parameters such as timeout, retries, test URL, and more. You can also:
- Enable detailed results (including response times, anonymity, and geo-location).
- Choose your preferred export format (TXT, CSV, or JSON).
- Set a custom User-Agent if desired.
- Use the Pause/Resume button to temporarily suspend or restart the checking process.

# Configuration

Within the GUI, you can set:
- **Timeout:** Maximum time (in seconds) for proxy requests.
- **Max Retries & Retry Delay:** Adjust the number of retry attempts and delay between retries.
- **Max Workers:** Number of concurrent threads.
- **Test URL:** URL used for testing the proxies (default is Google).
- **Custom User-Agent:** Specify a custom User-Agent header for requests.
- **Detailed Results:** Toggle to include extra details such as response time, anonymity, and geo-location.
- **Export Format:** Select from TXT, CSV, or JSON.
- **Proxy Sources:** Enter URLs for the proxy lists.

# Troubleshooting

- **Connection Errors:**  
  Adjust timeout or reduce the number of workers if many connection errors occur.
- **Empty Output Files:**  
  Verify that the proxy URLs are valid and accessible.
- **Performance:**  
  Detailed mode (with extra API calls) might slightly increase processing time.

# Contributing

Contributions are welcome! Fork the repository and submit pull requests with enhancements or bug fixes. Please follow the project's coding standards and include appropriate tests.

# License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.