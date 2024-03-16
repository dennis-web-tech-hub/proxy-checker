# Proxy Checker

## Description
Proxy Checker is a Python program that checks proxy servers for functionality and saves working proxies to a file.

## Installation
1. Ensure you have Python 3 installed.
2. Install the necessary libraries using pip:

   ```
   pip install -r requirements.txt
   ```
   
3. Download and run the script.

## Proxy Sources
This script uses a predefined list of URLs to check proxies. You can modify this list to include your own sources. If you're looking for a source of proxies, you might find [this repository](https://github.com/TheSpeedX/PROXY-List) by TheSpeedX useful. It contains a regularly updated list of proxies.

## Usage
Simply run the script, and it will start checking proxy servers from the predefined list of URLs. Working proxy servers will be saved to separate files based on their type (HTTP, HTTPS, SOCKS4, SOCKS5) within a directory named `proxies`.

## Logging
The program also logs to a file named `logs.txt`, which contains information about the number of proxies checked and the execution time.