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
import os

def rotodinamic_scraper(name):
    try:
        options = Options()
        options.headless = True
        driver = webdriver.Firefox(options=options)
        print("[INFO] Navigating to the page...")
        driver.get("https://webshop.rotodinamic.hr/" + name)

        time.sleep(2)
        # Handle age verification
        try:
            print("[INFO] Waiting for 'Dopusti selektirane' button...")
            cookie_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Dopusti selektiranje')]"))
            )
            cookie_button.click()
            print("[INFO] Clicked 'Dopusti selektirane' button.")
            time.sleep(3)
        except Exception as e:
            print(f"[WARN] Failed to click cookie button: {e}")


        try:
            # Wait for and fill in 'dan' (day)
            day_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "dan"))
            )
            day_input.clear()
            day_input.send_keys("04")

            # Fill in 'mjesec' (month)
            month_input = driver.find_element(By.ID, "mjesec")
            month_input.clear()
            month_input.send_keys("09")

            # Fill in 'godina' (year)
            year_input = driver.find_element(By.ID, "godina")
            year_input.clear()
            year_input.send_keys("1992")

            # Wait for and click the "Kreni" button
            kreni_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.blue-btn-age"))
            )
            kreni_button.click()

            print("[INFO] Form submitted successfully.")
            time.sleep(2)  # Wait to see what happens after submit

        except Exception as e:
            print(f"[ERROR] Something went wrong: {e}")

        
        # List to store all products from all pages
        all_products = []
        
        # Get products from the first page
        print("[INFO] Getting products from page 1...")
        content = driver.page_source
        soup = BeautifulSoup(content, "html.parser")
        items = soup.select("div.item.single-product")
        print(f"[INFO] Found {len(items)} product containers on page 1.")
        
        # Process products from the first page
        for idx, item in enumerate(items):
            title_elem = item.select_one("span.product-name")
            price_elem = item.select_one("span.price-new")
            if not (price_elem):
                price_elem = item.select_one("div.price span")
            size_elem = item.select_one("div.custom-fields-field-1")
            link_elem = item.select_one("a")

            if title_elem and price_elem:
                title_text = title_elem.get_text(strip=True)
                price_text = price_elem.get_text(strip=True)
                size_text = size_elem.get_text(strip=True) if size_elem else None
                link = link_elem["href"] if link_elem and "href" in link_elem.attrs else None
                img_elem = item.select_one("div.image img")
                img_url = img_elem["src"] if img_elem and img_elem.get("src") else None

                all_products.append({
                    "title": title_text,
                    "price": price_text,
                    "size": size_text,
                    "link": link,
                    "image": img_url
                })
            else:
                print(f"[WARN] Product {idx + 1}: Missing title or price.")
        
        # Handle pagination and collect products from subsequent pages
        current_page = 1
        has_more_pages = True

        while has_more_pages:
            try:
                print(f"[INFO] Scraping page {current_page}...")
                current_url = driver.current_url

                # Get products from the current page
                content = driver.page_source
                soup = BeautifulSoup(content, "html.parser")
                items = soup.select("div.item.single-product")
                print(f"[INFO] Found {len(items)} product containers on page {current_page}.")

                # Process products
                for idx, item in enumerate(items):
                    title_elem = item.select_one("span.product-name")
                    price_elem = item.select_one("span.price-new")
                    if not (price_elem):
                        price_elem = item.select_one("div.price span")
                    size_elem = item.select_one("div.custom-fields-field-1")
                    link_elem = item.select_one("a")

                    if title_elem and price_elem:
                        title_text = title_elem.get_text(strip=True)
                        price_text = price_elem.get_text(strip=True)
                        size_text = size_elem.get_text(strip=True) if size_elem else None
                        link = link_elem["href"] if link_elem and "href" in link_elem.attrs else None
                        img_elem = item.select_one("div.image img")
                        img_url = img_elem["src"] if img_elem and img_elem.get("src") else None

                        all_products.append({
                            "title": title_text,
                            "price": price_text,
                            "size": size_text,
                            "link": link,
                            "image": img_url
                        })
                    else:
                        print(f"[WARN] Product {idx + 1} on page {current_page}: Missing title or price.")

                # Check for link to the next page
                next_page_number = current_page + 1
                next_page_link = soup.select_one(f'ul.pagination li a[href*="page={next_page_number}"]')

                if next_page_link:
                    href = next_page_link["href"]
                    print(f"[INFO] Clicking link to page {next_page_number}: {href}")
                    driver.get(href)
                    WebDriverWait(driver, 10).until(EC.url_changes(current_url))
                    time.sleep(2)
                    current_page += 1
                else:
                    print("[INFO] No more pages found.")
                    has_more_pages = False

            except Exception as e:
                print(f"[ERROR] Pagination failed: {e}")
                has_more_pages = False


        print("[INFO] Getting fully loaded page source...")
        driver.quit()
        print("[INFO] Browser closed.")

        # Sanitize the name to avoid directory creation from slashes
        safe_name = name.replace("/", "-")

        # Make path relative to this script file, not the current working directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "../../data/rotodinamic", safe_name + "_rotodinamic.json")
        output_path = os.path.normpath(output_path)  # Clean up the path

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

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