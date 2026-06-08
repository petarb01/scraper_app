from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import time
import sys
import os

def promili_scraper(name):
    base_url = "https://www.promili.hr"
    try:
        options = Options()
        options.headless = True
        driver = webdriver.Firefox(options=options)
        print("[INFO] Navigating to the page...")
        driver.get(base_url + "/shop/category/" + name)
        time.sleep(5)
        # Handle age verification
        try:
            da_button = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button.btn.btn-primary.px-5.py-2.fw-bold"))
            )
            da_button.click()
            time.sleep(5)
        except Exception as e:
            print(f"[WARN] Failed to click 'DA': {e}")


        # Keep clicking the load more button until it's not 'U\u010ditaj vi\u0161e'
        


        print("[INFO] Getting fully loaded page source...")
        content = driver.page_source
        driver.quit()
        print("[INFO] Browser closed.")

        print("[INFO] Parsing content with BeautifulSoup...")
        soup = BeautifulSoup(content, "html.parser")

        products = []
        items = soup.select("div.oe_product.g-col-6.g-col-md-4.g-col-lg-3 ")
        print(f"[INFO] Found {len(items)} product containers.")

        for idx, item in enumerate(items):
            title_elem = item.select_one("a.text-decoration-none")
            price_elem = item.select_one("span.oe_currency_value")
            size_elem = item.select_one("span.o_ribbons.o_not_editable.o_wsale_ribbon.o_right")

            if title_elem and price_elem:
                title_text = title_elem.get_text(strip=True)
                price_text = price_elem.get_text(strip=True)
                size_text = size_elem.get_text(strip=True) if size_elem else None
                link = urljoin(base_url, title_elem["href"]) if title_elem and "href" in title_elem.attrs else None
                img_elem = item.select_one("span.oe_product_image_img_wrapper_primary img")
                img_url = urljoin(base_url, img_elem["src"]) if img_elem and img_elem.get("src") else None

                products.append({
                    "title": title_text,
                    "price": price_text,
                    "size": size_text,
                    "link": link,
                    "image": img_url
                })
            else:
                print(f"[WARN] Product {idx + 1}: Missing title or price.")

        # Sanitize the name to avoid directory creation from slashes
        safe_name = name.replace("/", "-")

        # Make path relative to this script file, not the current working directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "../../data/promili", safe_name + "_promili.json")
        output_path = os.path.normpath(output_path)  # Clean up the path

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        print(f"[INFO] Saving {len(products)} products to {output_path}...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)

        print("[INFO] Done!")

    except Exception as e:
        print(f"[ERROR] Something went wrong: {e}", file=sys.stderr)

    finally:
        try:
            driver.quit()
        except:
            pass
