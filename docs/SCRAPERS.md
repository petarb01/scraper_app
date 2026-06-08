# Scrapers Documentation

Complete guide to the web scraping system, how scrapers work, and how to add new ones.

## Overview

The project uses **Selenium with Firefox** in headless mode to scrape product data from 5 Croatian e-commerce websites.

### Current Scrapers

| Scraper | Website | Categories | Products | Status |
|---------|---------|-----------|----------|--------|
| **ecuga** | ecuga.com | 5 | ~1,140 | ✅ Working |
| **cugaklik** | cugaklik.hr | 4 | ~891 | ✅ Working |
| **promili** | promili.hr | 8 | ~269 | ✅ Working |
| **diskontfumar** | diskontfumar.hr | 4 | ~872 | ✅ Working |
| **rotodinamic** | rotodinamic.hr | Various | ~1,800 | ✅ Working |

## Architecture

### Project Structure

```
scraper/
├── scrapers/                  # Individual scraper modules
│   ├── ecuga/
│   │   ├── __init__.py       # Scraper executor
│   │   └── ecuga_scraper.py  # Scraper logic
│   ├── cugaklik/
│   │   ├── __init__.py
│   │   └── cugaklik_scraper.py
│   ├── promili/
│   ├── diskontfumar/
│   └── rotodinamic/
├── data/                      # Scraped JSON data
│   ├── ecuga/
│   ├── cugaklik/
│   └── ...
├── utils/                     # Shared utilities
│   └── server_helper.py
└── run_all_scrapers.py       # Orchestrator script
```

### How Scrapers Work

```
┌─────────────────────────────────────────┐
│         Scraper Execution Flow          │
├─────────────────────────────────────────┤
│                                         │
│  1. Launch Firefox (headless)           │
│  2. Navigate to category page           │
│  3. Wait for dynamic content            │
│  4. Extract product data                │
│  5. Navigate to next page (if exists)   │
│  6. Repeat until all pages scraped      │
│  7. Save to JSON file                   │
│  8. Optionally save to database         │
│  9. Close browser                       │
│                                         │
└─────────────────────────────────────────┘
```

## Running Scrapers

### All Scrapers (Orchestrator)

```bash
cd scraper
python3 run_all_scrapers.py
```

**Features:**
- Runs scrapers sequentially (one at a time)
- Comprehensive logging
- Error handling and timeout protection
- Execution summary with timing stats
- 10-second delay between scrapers

### Individual Scraper

```bash
cd scraper/scrapers/ecuga
python3 __init__.py
```

**Or:**
```bash
python3 -m scraper.scrapers.ecuga
```

### With Database Integration

```bash
# Enable database writes
export USE_DATABASE=1

# Run scrapers
cd scraper
python3 run_all_scrapers.py
```

## Scraper Implementation

### Basic Scraper Structure

```python
# scraper/scrapers/example/__init__.py

import asyncio
from .example_scraper import scrape_example

async def main():
    """Main entry point for the scraper."""
    print("Starting Example scraper...")

    try:
        await scrape_example()
        print("Example scraper completed successfully!")
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
```

### Scraper Logic

```python
# scraper/scrapers/example/example_scraper.py

import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options

async def scrape_example():
    """Scrape products from example.com"""

    # Category configurations
    categories = [
        {
            "name": "whisky",
            "url": "https://example.com/category/whisky",
            "filename": "whisky_example.json"
        },
        # ... more categories
    ]

    # Setup Firefox options
    firefox_options = Options()
    firefox_options.add_argument("--headless")  # Run without GUI
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-dev-shm-usage")

    # Initialize driver
    driver = webdriver.Firefox(options=firefox_options)

    try:
        for category in categories:
            print(f"Scraping {category['name']}...")
            products = scrape_category(driver, category['url'])

            # Save to JSON
            save_to_json(products, category['filename'])

            # Optionally save to database
            if os.getenv('USE_DATABASE') == '1':
                save_to_database(products, category['name'])

    finally:
        driver.quit()

def scrape_category(driver, url):
    """Scrape products from a category page."""
    driver.get(url)

    # Wait for products to load
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CLASS_NAME, "product-item"))
    )

    products = []

    # Extract products
    product_elements = driver.find_elements(By.CLASS_NAME, "product-item")

    for element in product_elements:
        try:
            title = element.find_element(By.CLASS_NAME, "product-title").text
            price = element.find_element(By.CLASS_NAME, "product-price").text
            url = element.find_element(By.TAG_NAME, "a").get_attribute("href")

            products.append({
                "title": title,
                "price": price,
                "link": url
            })
        except Exception as e:
            print(f"Error extracting product: {e}")
            continue

    return products

def save_to_json(products, filename):
    """Save products to JSON file."""
    output_path = f"scraper/data/example/{filename}"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(products)} products to {output_path}")
```

## Adding a New Scraper

### Step 1: Create Directory Structure

```bash
mkdir -p scraper/scrapers/newsite
mkdir -p scraper/data/newsite
touch scraper/scrapers/newsite/__init__.py
touch scraper/scrapers/newsite/newsite_scraper.py
```

### Step 2: Implement Scraper

Copy and modify an existing scraper:

```bash
cp scraper/scrapers/ecuga/ecuga_scraper.py scraper/scrapers/newsite/newsite_scraper.py
cp scraper/scrapers/ecuga/__init__.py scraper/scrapers/newsite/__init__.py
```

Edit `newsite_scraper.py`:
1. Update URLs and selectors
2. Adjust data extraction logic
3. Update category configurations

### Step 3: Test Individual Scraper

```bash
cd scraper/scrapers/newsite
python3 __init__.py
```

Check output in `scraper/data/newsite/`

### Step 4: Add to Orchestrator

Edit `scraper/run_all_scrapers.py`:

```python
SCRAPERS = [
    # ... existing scrapers
    {
        "name": "newsite",
        "path": "scrapers/newsite/__init__.py",
        "description": "NewSite website scraper"
    },
]
```

### Step 5: Add to Database

Update `database/schema.sql`:

```sql
INSERT INTO sources (name, url) VALUES
('NewSite', 'https://newsite.com');
```

Recreate database or insert manually:

```bash
docker exec price_scraper_db psql -U postgres -d price_scraper -c \
  "INSERT INTO sources (name, url) VALUES ('NewSite', 'https://newsite.com');"
```

## Scraper Best Practices

### 1. Respect Website Policies

- Check `robots.txt`
- Add delays between requests
- Don't overwhelm servers
- Use reasonable user agents

```python
from time import sleep

# Add delay between pages
for page in pages:
    scrape_page(page)
    sleep(2)  # 2-second delay
```

### 2. Error Handling

```python
try:
    products = scrape_category(driver, url)
except TimeoutException:
    print(f"Timeout while loading {url}")
    products = []
except NoSuchElementException:
    print(f"Product elements not found on {url}")
    products = []
except Exception as e:
    print(f"Unexpected error: {e}")
    products = []
```

### 3. Dynamic Content Handling

```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Wait for element to be visible
wait = WebDriverWait(driver, 30)
element = wait.until(
    EC.visibility_of_element_located((By.ID, "product-list"))
)

# Wait for element to be clickable
button = wait.until(
    EC.element_to_be_clickable((By.ID, "load-more"))
)
button.click()
```

### 4. Pagination

```python
def scrape_all_pages(driver, base_url):
    """Scrape all pages of a category."""
    all_products = []
    page = 1

    while True:
        url = f"{base_url}?page={page}"
        driver.get(url)

        products = scrape_current_page(driver)

        if not products:
            break  # No more products

        all_products.extend(products)
        page += 1

        sleep(2)  # Polite delay

    return all_products
```

### 5. Data Validation

```python
def validate_product(product):
    """Validate product data."""
    required_fields = ['title', 'price', 'link']

    for field in required_fields:
        if not product.get(field):
            return False

    # Validate price format
    if not is_valid_price(product['price']):
        return False

    return True

def is_valid_price(price_str):
    """Check if price string is valid."""
    import re
    # Matches "99.99 €", "99,99€", etc.
    pattern = r'\d+[.,]?\d*\s*€'
    return bool(re.search(pattern, price_str))
```

## Logging

### Setup Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scraper.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### Use Logger

```python
logger.info(f"Starting {category['name']} scraper")
logger.debug(f"Navigating to {url}")
logger.warning(f"Retrying request: {retry_count}/3")
logger.error(f"Failed to extract price: {e}")
```

## Database Integration

### Saving to Database

```python
from database.db_utils import DatabaseConfig, ProductRepository
import os

def save_to_database(products, category_name, source_name):
    """Save products to PostgreSQL database."""

    if os.getenv('USE_DATABASE') != '1':
        return

    config = DatabaseConfig()
    repo = ProductRepository(config)

    for product in products:
        repo.insert_product(
            source_name=source_name,
            category_name=category_name,
            title=product['title'],
            price=parse_price(product['price']),
            url=product['link']
        )

    logger.info(f"Saved {len(products)} products to database")

def parse_price(price_str):
    """Extract numeric price from string."""
    import re
    match = re.search(r'(\d+[.,]\d+)', price_str)
    if match:
        return float(match.group(1).replace(',', '.'))
    return None
```

## Troubleshooting

### Browser Not Found

```bash
# Install Firefox
sudo apt-get install firefox

# Or Firefox ESR
sudo apt-get install firefox-esr
```

### Geckodriver Not Found

```bash
# Download geckodriver
wget https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz

# Extract and install
tar -xvzf geckodriver-v0.35.0-linux64.tar.gz
sudo mv geckodriver /usr/local/bin/
sudo chmod +x /usr/local/bin/geckodriver
```

### Timeout Errors

```python
# Increase timeout
wait = WebDriverWait(driver, 60)  # Increase from 30 to 60 seconds

# Or retry
max_retries = 3
for attempt in range(max_retries):
    try:
        driver.get(url)
        element = wait.until(EC.presence_of_element_located((By.ID, "products")))
        break
    except TimeoutException:
        if attempt == max_retries - 1:
            raise
        logger.warning(f"Retry {attempt + 1}/{max_retries}")
        sleep(5)
```

### Element Not Found

```python
# Use more specific selectors
product = driver.find_element(By.CSS_SELECTOR, "div.product-card[data-product-id]")

# Or wait for element
from selenium.webdriver.support import expected_conditions as EC
element = WebDriverWait(driver, 30).until(
    EC.presence_of_element_located((By.CLASS_NAME, "product"))
)

# Handle missing elements gracefully
try:
    price = product.find_element(By.CLASS_NAME, "price").text
except NoSuchElementException:
    price = None
```

### Headless Mode Issues

```python
# If headless doesn't work, try with GUI
firefox_options = Options()
# firefox_options.add_argument("--headless")  # Comment out

# Or use Xvfb (virtual display)
from pyvirtualdisplay import Display

display = Display(visible=0, size=(1920, 1080))
display.start()

driver = webdriver.Firefox()
# ... scraping code ...

driver.quit()
display.stop()
```

## Performance Optimization

### 1. Disable Images/CSS

```python
firefox_options = Options()
firefox_options.set_preference("permissions.default.image", 2)  # Disable images
firefox_options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", False)
```

### 2. Reuse Browser Instance

```python
# Instead of creating new driver for each category
driver = webdriver.Firefox(options=firefox_options)

for category in categories:
    products = scrape_category(driver, category['url'])
    # ...

driver.quit()
```

### 3. Parallel Scraping (Advanced)

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def scrape_all_parallel():
    """Scrape multiple categories in parallel."""
    categories = [...]

    with ThreadPoolExecutor(max_workers=3) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, scrape_category, cat)
            for cat in categories
        ]
        results = await asyncio.gather(*tasks)

    return results
```

## Monitoring

### Scraper Logs

```bash
# View logs
tail -f logs/scraper_run_*.log

# Check last run summary
cat logs/last_run_summary.json
```

### Scheduled Execution

See [DEPLOYMENT.md](../DEPLOYMENT.md) for setting up cron/systemd for automated scraping.

---

**For more information, see [README.md](../README.md)**
