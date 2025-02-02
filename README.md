<div align="center">
   <img src="src/img/icon.png" alt="ProxyChecker" width="200" height="200"> 
   <h1>ProxyChecker</h1> 
   <p>A concurrent and efficient proxy checker for testing HTTP, SOCKS4, and SOCKS5 proxies, using multi-threading and automatic retry mechanisms.</p> 
   <a href="#features"><strong>Features</strong></a> •
   <a href="#installation"><strong>Installation</strong></a> •
   <a href="#usage"><strong>Usage</strong></a> •
   <a href="#configuration"><strong>Configuration</strong></a> •
   <a href="#troubleshooting"><strong>Troubleshooting</strong></a> •
   <a href="#contributing"><strong>Contributing</strong></a>
</div>

---

# Overview

**ProxyChecker** is a Python tool designed to verify the functionality of a list of HTTP, SOCKS4, and SOCKS5 proxies by sending test requests. It supports concurrent requests for efficient performance, with configurable parameters to control timeouts, retry attempts, and the number of concurrent workers.

## Features

- **Multi-threaded Proxy Checking**: Uses Python's `ThreadPoolExecutor` for concurrent proxy testing.
- **Configurable Timeout and Retries**: Customize timeout per request and retry logic to handle intermittent network issues.
- **Supports HTTP, SOCKS4, SOCKS5 Proxies**: Works with multiple proxy types and fetches proxies from configurable URLs.
- **Automatic Output Saving**: Saves lists of working proxies for each type in a dedicated directory.
- **GUI and Console Modes**: Run with a user-friendly PyQt6 interface or via command-line arguments.

## Installation

### Prerequisites

- Python 3.6 or later
- `requests` package for handling HTTP requests
- `PyQt6` package for the GUI (if you plan to run the GUI mode)

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

   _(If you don't have a `requirements.txt`, you can install the necessary packages manually:)_

   ```bash
   pip install requests PyQt6
   ```

## Usage

### Running in GUI Mode

To launch the graphical user interface, run:

```bash
python proxy-checker.py
```

This will open a window where you can configure parameters (e.g., timeout, max retries, retry delay, and max workers), select proxy types to check, and view live progress logs.

### Running in Console Mode

To run ProxyChecker in console mode (without the GUI), use the `--console` flag:

```bash
python proxy-checker.py --console
```

You can also customize settings via command-line arguments, for example:

```bash
python proxy-checker.py --console --timeout 5 --max-retries 4 --retry-delay 2.0 --max-workers 100
```

## Configuration

You can configure the following parameters in the `ProxyChecker` class or pass them as command-line arguments:

- **proxy_urls**: Dictionary of URLs to fetch proxy lists for HTTP, SOCKS4, and SOCKS5.
- **timeout**: Timeout for each proxy request (default: 1 second).
- **max_retries**: Maximum retry attempts if fetching proxies fails (default: 3).
- **retry_delay**: Delay between retries (default: 1.0 seconds).
- **max_workers**: Maximum number of concurrent threads for proxy checking (default: 50).

Example of custom initialization:

```python
proxy_urls = {
    "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
}

checker = ProxyChecker(proxy_urls, timeout=2, max_retries=5, retry_delay=1.5, max_workers=50)
checker.run()
```

## Troubleshooting

- **Connection Errors**: If you see multiple connection errors, consider lowering `max_workers` or increasing `timeout`.
- **Empty Output**: If the output files are empty, verify that the proxy URLs are accessible and returning valid proxy lists.
- **Network Limits**: Avoid setting very high concurrency (e.g., `max_workers=100`) as it may cause network throttling or rate-limiting issues.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your enhancements or bug fixes. Ensure your code adheres to the project's coding standards and includes appropriate tests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
