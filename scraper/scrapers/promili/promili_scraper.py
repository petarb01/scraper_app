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

def promili_scraper(name):
    try:
        options = Options()
        options.headless = True
        driver = webdriver.Firefox(options=options)
        print("[INFO] Navigating to the page...")
        driver.get("https://www.promili.hr/shop/category/" + name)

        # Handle age verification
        try:
            da_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Imam')]"))
            )
            da_button.click()
            time.sleep(5)
        except Exception as e:
            print(f"[WARN] Failed to click 'DA': {e}")

        # Handle cookie banner
        try:
            print("[INFO] Waiting for 'Dopusti neophodne' button...")
            cookie_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Dopusti neophodne')]"))
            )
            cookie_button.click()
            print("[INFO] Clicked 'Dopusti neophodne' button.")
            time.sleep(3)
        except Exception as e:
            print(f"[WARN] Failed to click cookie button: {e}")

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
            title_elem = item.select_one("a.text-primary.text-decoration-none")
            price_elem = item.select_one("span.oe_currency_value")
            link_elem = item.select_one("a.oe_product_image_link.d-block.position-relative")

            if title_elem and price_elem:
                title_text = title_elem.get_text(strip=True)
                price_text = price_elem.get_text(strip=True)
                link = link_elem["href"] if link_elem and "href" in link_elem.attrs else None

                

                products.append({
                    "title": title_text,
                    "price": price_text,
                    "link": link
                })
            else:
                print(f"[WARN] Product {idx + 1}: Missing title or price.")

        output_path = "../../data/promili/" + name + "_ecuga.json"
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
