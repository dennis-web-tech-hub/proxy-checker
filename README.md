<div align="center">
   <img src="src/img/icon.png" alt="ProxyChecker" width="200" height="200"> 
   <h1>ProxyChecker</h1> 
   <p>A concurrent and efficient proxy checker for testing HTTP, SOCKS4, and SOCKS5 proxies, featuring multi-threading, automatic retry mechanisms, and advanced proxy details.</p> 
   <a href="#features"><strong>Features</strong></a> •
   <a href="#installation"><strong>Installation</strong></a> •
   <a href="#usage"><strong>Usage</strong></a> •
   <a href="#configuration"><strong>Configuration</strong></a> •
   <a href="#troubleshooting"><strong>Troubleshooting</strong></a> •
   <a href="#contributing"><strong>Contributing</strong></a>
</div>

---

# Overview

**ProxyChecker** is a Python tool designed to verify the functionality of proxy lists (HTTP, SOCKS4, and SOCKS5) by sending test requests. It supports concurrent requests for efficient performance, offers detailed results with proxy anonymity detection and geo-location lookup, and automatically saves the working proxies. This version is exclusively GUI-based with a modern interface built using PyQt6.

# Features

- **Multi-threaded Proxy Checking:**  
  Utilizes Python's `ThreadPoolExecutor` for concurrent proxy testing.

- **Configurable Timeout and Retries:**  
  Customize the timeout per request and retry logic to handle network issues.

- **Supports HTTP, SOCKS4, SOCKS5 Proxies:**  
  Easily fetch proxy lists from configurable URLs.

- **Detailed Proxy Analysis:**  
  When enabled, detailed mode provides:
  - **Response Times:** Measures how long each proxy takes to respond.
  - **Anonymity Detection:** Determines whether a proxy is transparent or anonymous.
  - **Geo-Location Lookup:** Fetches country, region, and city data for each working proxy.

- **Multiple Export Formats:**  
  Save working proxy results as plain text (TXT), CSV, or JSON for further processing.

- **GUI Application:**  
  Built with PyQt6, offering an intuitive interface with progress bars, log output, and settings dialogs.

- **Update Checker:**  
  Quickly check for the latest release version directly from the GUI.

# Installation

### Prerequisites

- Python 3.6 or later
- `requests` package for handling HTTP requests
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

Simply run the following command to launch the GUI:

```bash
python proxy-checker.py
```

Once the GUI opens, you can configure parameters such as timeout, max retries, retry delay, and the number of concurrent workers. You can also choose to enable detailed results (which include response times, anonymity, and geo-location data) and select your preferred export format (TXT, CSV, or JSON).

# Configuration

Within the GUI, you can configure:
- **Timeout:** Maximum seconds for proxy requests.
- **Max Retries & Retry Delay:** Controls the retry logic when fetching proxies.
- **Max Workers:** Sets the level of concurrency.
- **Test URL:** The URL used to validate the proxies (default is Google).
- **Detailed Results:** Toggle to include extra details like response time, anonymity, and geo-location.
- **Export Format:** Choose from TXT, CSV, or JSON for saving the results.
- **Proxy Sources:** URLs from which the proxy lists are fetched.

# Troubleshooting

- **Connection Errors:**  
  Adjust the timeout or reduce the number of concurrent workers if you encounter many connection errors.
- **Empty Output Files:**  
  Ensure that the proxy URLs are valid and accessible.
- **Detailed Mode Performance:**  
  Note that enabling detailed results (with anonymity and geo-location checks) might slightly increase processing time due to extra API calls.

# Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your enhancements or bug fixes. Ensure your code adheres to the project's coding standards and includes appropriate tests.

# License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.