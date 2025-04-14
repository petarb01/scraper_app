from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from bs4 import BeautifulSoup
import json
import time
import sys

def diskontfumar_scraper(name):
    try:
        options = Options()
        options.headless = True
        driver = webdriver.Firefox(options=options)
        print("[INFO] Navigating to the page...")
        driver.get("https://www.diskontfumar.hr/" + name)

        time.sleep(2)
        # Handle age verification
        try:
            da_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.ok-button.button-1"))
            )
            da_button.click()
            time.sleep(5)
        except Exception as e:
            print(f"[WARN] Failed to click 'DA': {e}")


        try:
            print("[INFO] Waiting for 'Slažem se' button...")
            cookie_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Odbaci sve')]"))
            )
            cookie_button.click()
            print("[INFO] Clicked 'Slažem se' button.")
            time.sleep(3)
        except Exception as e:
            print(f"[WARN] Failed to click cookie button: {e}")    
        
        # List to store all products from all pages
        all_products = []
        
        # Get products from the first page
        print("[INFO] Getting products from page 1...")
        content = driver.page_source
        soup = BeautifulSoup(content, "html.parser")
        items = soup.select("div.product-item")
        print(f"[INFO] Found {len(items)} product containers on page 1.")
        
        # Process products from the first page
        for idx, item in enumerate(items):
            title_elem = item.select_one("h2.product-title a")
            price_elem = item.select_one("span.price.actual-price")
            link_elem = item.select_one("a")


            
            
            if title_elem and price_elem:
                title_text = title_elem.get_text(strip=True)
                price_text = price_elem.get_text(strip=True)
                link = link_elem["href"] if link_elem and "href" in link_elem.attrs else None
                
                all_products.append({
                    "title": title_text,
                    "price": price_text,
                    "link": link
                })
            else:
                print(f"[WARN] Product {idx + 1}: Missing title or price.")
        
        # Handle pagination and collect products from subsequent pages
        current_page = 1
        has_more_pages = True
        
        while has_more_pages:
            current_page += 1
            try:
                current_url = driver.current_url
                print(current_url)
                print(f"[INFO] Clicking pagination to page {current_page}...")

                # XPath for targeting the exact page number
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//a[@data-page='{current_page}']"))
                )
                next_button.click()

                # Wait for the page to change (confirm URL change)
                WebDriverWait(driver, 10).until(
                    EC.url_changes(current_url)
                )
                print(f"[INFO] Pagination successful, now on page {current_page}")
                time.sleep(2)
                
                # Get products from the current page
                print(f"[INFO] Getting products from page {current_page}...")
                content = driver.page_source
                soup = BeautifulSoup(content, "html.parser")
                items = soup.select("div.item-box")
                print(f"[INFO] Found {len(items)} product containers on page {current_page}.")
                
                # Process products from the current page
                for idx, item in enumerate(items):
                    title_elem = item.select_one("h2.product-title")
                    price_elem = item.select_one("span.price.actual-price")
                    link_elem = item.select_one("a")

                    if title_elem and price_elem:
                        title_text = title_elem.get_text(strip=True)
                        price_text = price_elem.get_text(strip=True)
                        link = link_elem["href"] if link_elem and "href" in link_elem.attrs else None

                        all_products.append({
                            "title": title_text,
                            "price": price_text,
                            "link": link
                        })
                    else:
                        print(f"[WARN] Product {idx + 1} on page {current_page}: Missing title or price.")
                
            except Exception as e:
                print(f"[INFO] No more pages available or error navigating: {e}")
                has_more_pages = False

        print("[INFO] Getting fully loaded page source...")
        driver.quit()
        print("[INFO] Browser closed.")

        output_path = "../../data/diskontfumar/" + name + "_diskontfumar.json"
        print(f"[INFO] Saving {len(all_products)} products to {output_path}...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)

        print("[INFO] Done!")

    except Exception as e:
        print(f"[ERROR] Something went wrong: {e}", file=sys.stderr)

    finally:
        try:
            driver.quit()
        except:
            pass