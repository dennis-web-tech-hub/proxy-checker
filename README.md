# Proxy Checker

This script is designed to check the availability of HTTP, SOCKS4, and SOCKS5 proxies from various online sources. It uses multithreading to efficiently process large lists of proxies, saving the working ones into separate files based on their type.

## Features

- Fetches proxy lists from specified URLs.
- Checks the availability of each proxy.
- Saves working proxies into separate files for HTTP, SOCKS4, and SOCKS5.
- Uses multithreading for fast execution.
- Configurable timeout and number of threads.

## Prerequisites

- Python 3.x
- Required Python packages:
  - `requests`
  - `colorama`

You can install the required packages using pip:

```bash
pip install requests colorama
```

## Usage

1. **Clone the repository or download the script.**

2. **Run the script:**

   ```bash
   python proxy_checker.py
   ```

   The script will start checking proxies and will display the progress in the terminal. 

3. **Results:**

   Working proxies will be saved in the `proxies` directory, categorized by their type (http, socks4, socks5).

## Configuration

You can adjust the configurable parameters at the top of the script:

- `TIMEOUT`: The timeout for checking each proxy (default is 1 second).
- `MAX_WORKERS`: The maximum number of threads to use (default is 500).

```python
# Configurable parameters
TIMEOUT = 1
MAX_WORKERS = 500
```

## Output

The script prints the following information to the console:

- The number of proxies checked for each type.
- The number of working proxies found.
- The total execution time.

Example output:

```
Checking 100 http proxies from https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt. This may take some time...
Checking 100 socks4 proxies from https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt. This may take some time...
Checking 100 socks5 proxies from https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt. This may take some time...
Checked 300 proxies. Working proxies: 45.
Execution time: 0 minutes 30 seconds.
```

## Directory Structure

- `proxy_checker.py`: The main script file.
- `proxies/`: Directory where the working proxies will be saved.
  - `http.txt`: Working HTTP proxies.
  - `socks4.txt`: Working SOCKS4 proxies.
  - `socks5.txt`: Working SOCKS5 proxies.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Acknowledgements

- Proxy lists sourced from [TheSpeedX/PROXY-List](https://github.com/TheSpeedX/PROXY-List).