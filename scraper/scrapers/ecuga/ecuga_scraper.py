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

def ecuga_scraper(name):
    try:
        options = Options()
        options.headless = True
        driver = webdriver.Firefox(options=options)
        print("[INFO] Navigating to the page...")
        driver.get("https://ecuga.com/katalog/" + name)

        # Handle age verification
        try:
            da_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-f9183068-6.jSKaYH"))
            )
            da_button.click()
            time.sleep(5)
        except Exception as e:
            print(f"[WARN] Failed to click 'DA': {e}")

        # Handle cookie banner
        try:
            print("[INFO] Waiting for 'Dopusti selektirane' button...")
            cookie_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Dopusti selektirane')]"))
            )
            cookie_button.click()
            print("[INFO] Clicked 'Dopusti selektirane' button.")
            time.sleep(3)
        except Exception as e:
            print(f"[WARN] Failed to click cookie button: {e}")

        # Keep clicking the load more button until it's not 'U\u010ditaj vi\u0161e'
        def load_all_content(driver, max_attempts=15, timeout=30):
            attempts = 0
            last_page_height = driver.execute_script("return document.body.scrollHeight")
            
            while attempts < max_attempts:
                try:
                    # Wait for the button to be clickable
                    wait = WebDriverWait(driver, timeout)
                    load_more_button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-da102c16-0.fRakmM"))
                    )
                    
                    button_text = load_more_button.text.strip()
                    if "Učitaj više" in button_text:
                        # Scroll button into view
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                        time.sleep(1)
                        
                        # Try direct click first
                        try:
                            load_more_button.click()
                        except:
                            # If direct click fails, try JavaScript click
                            driver.execute_script("arguments[0].click();", load_more_button)
                        
                        # Wait for new content to load
                        time.sleep(2)
                        
                        # Check if page height changed (indicating new content)
                        current_height = driver.execute_script("return document.body.scrollHeight")
                        if current_height == last_page_height:
                            # If no new content loaded after waiting, try again or break
                            attempts += 1
                            if attempts >= 3:
                                print("[WARN] Page height didn't change after clicking, possible loading issue")
                                time.sleep(2)
                                if attempts >= 5:
                                    print("[ERROR] No new content loaded after 5 attempts - stopping")
                                    return False
                        else:
                            # Reset attempts counter on successful load
                            attempts = 0
                            last_page_height = current_height
                    else:
                        print(f"[INFO] Button changed to '{button_text}' — stopping.")
                        return True
                        
                except NoSuchElementException:
                    print("[INFO] 'Učitaj više' button not found — done loading.")
                    return True
                except ElementClickInterceptedException:
                    print("[WARN] Button not clickable, retrying...")
                    # Try to close any overlays or popups
                    try:
                        # Look for common overlay close buttons
                        close_buttons = driver.find_elements(By.CSS_SELECTOR, 
                                                    ".close-button, .modal-close, button[aria-label='Close']")
                        if close_buttons:
                            close_buttons[0].click()
                            time.sleep(1)
                    except:
                        pass
                    
                    # Scroll and try again
                    driver.execute_script("window.scrollBy(0, 100);")
                    time.sleep(2)
                    attempts += 1
                except Exception as e:
                    print(f"[ERROR] Unexpected error: {str(e)}")
                    attempts += 1
                    time.sleep(2)
            
            print(f"[WARN] Reached maximum {max_attempts} attempts - may not have loaded all content")
            return False

        load_all_content(driver)


        print("[INFO] Getting fully loaded page source...")
        content = driver.page_source
        driver.quit()
        print("[INFO] Browser closed.")

        print("[INFO] Parsing content with BeautifulSoup...")
        soup = BeautifulSoup(content, "html.parser")

        products = []
        items = soup.select("li.sc-5ce8ced0-0.bcCFxH")
        print(f"[INFO] Found {len(items)} product containers.")

        for idx, item in enumerate(items):
            title_elem = item.select_one("h3.sc-5ce8ced0-6.efPlgI")
            price_elem = item.select_one("span.sc-7fb65671-2.icPbuR")
            link_elem = item.select_one("a")

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

        output_path = "../../data/ecuga/" + name + "_ecuga.json"
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
