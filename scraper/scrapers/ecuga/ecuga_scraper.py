from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException
from bs4 import BeautifulSoup

import json
import time
import sys
import os

def ecuga_scraper(name):
    base_url = "https://ecuga.com"
    try:
        options = Options()
        options.headless = True
        driver = webdriver.Firefox(options=options)
        print("[INFO] Navigating to the page...")
        driver.get(base_url + "/katalog/" + name)
        time.sleep(2)  # Let the page start rendering before checking for dialogs

        # Age verification appears first and blocks everything — handle it before newsletter
        try:
            da_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='DA' or normalize-space()='Da' or normalize-space()='da']"))
            )
            da_button.click()
            print("[INFO] Age verification confirmed.")
            time.sleep(3)
        except TimeoutException:
            print("[INFO] Age verification not present — skipping.")
        except Exception as e:
            print(f"[WARN] Age verification failed unexpectedly: {e}")

        # Newsletter popup — wait up to 30s, non-fatal if missing
        print("[INFO] Waiting for newsletter popup (up to 30s)...")
        try:
            sib_iframe = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe.wpiam-iframe, iframe[src*='sibforms.com']"))
            )
            driver.switch_to.frame(sib_iframe)
            dismissed = False
            try:
                close_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='cross-button'], .sib-cross_button, #cross-button"))
                )
                close_btn.click()
                print("[INFO] Newsletter dismissed.")
                time.sleep(0.5)
                dismissed = True
            except Exception:
                print("[WARN] Newsletter close button not clickable — removing iframe via JS.")
            finally:
                driver.switch_to.default_content()
            if not dismissed:
                try:
                    driver.execute_script(
                        "const f = document.querySelector('iframe.wpiam-iframe'); if (f) f.remove();"
                    )
                    print("[INFO] Newsletter iframe removed via JS.")
                except Exception as e:
                    print(f"[WARN] Could not remove newsletter iframe: {e}")
        except TimeoutException:
            print("[INFO] No newsletter popup appeared — continuing.")
        except Exception as e:
            print(f"[WARN] Newsletter handling failed: {e}")
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
        # Wait for the iframe to leave the DOM before proceeding
        try:
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "iframe.wpiam-iframe"))
            )
        except Exception:
            pass

        # Cookie banner — newsletter iframe may still be covering it, so fall back to JS click
        try:
            cookie_button = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Dopusti selektirane')]"))
            )
            try:
                cookie_button.click()
            except ElementClickInterceptedException:
                print("[INFO] Cookie button intercepted — using JS click.")
                driver.execute_script("arguments[0].click();", cookie_button)
            print("[INFO] Cookie banner dismissed.")
            time.sleep(3)
        except TimeoutException:
            print("[INFO] Cookie banner not present — skipping.")
        except Exception as e:
            print(f"[WARN] Cookie banner failed unexpectedly: {e}")

        def load_all_content(max_attempts=10):
            last_height = driver.execute_script("return document.body.scrollHeight")
            attempts = 0

            while attempts < max_attempts:
                # Scroll to bottom to trigger rendering of the load-more button
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

                try:
                    btn = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Učitaj više')]"))
                    )

                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    try:
                        btn.click()
                    except ElementClickInterceptedException:
                        print("[WARN] Load-more click intercepted — using JS click.")
                        driver.execute_script("arguments[0].click();", btn)

                    print("[INFO] Clicked 'Učitaj više', waiting for new content...")
                    time.sleep(3)
                    current_height = driver.execute_script("return document.body.scrollHeight")
                    if current_height == last_height:
                        attempts += 1
                        if attempts >= 5:
                            print("[WARN] Page height unchanged after 5 clicks — stopping.")
                            return
                    else:
                        attempts = 0
                        last_height = current_height

                except (NoSuchElementException, TimeoutException):
                    print("[INFO] 'Učitaj više' button not found — all content loaded.")
                    return
                except ElementClickInterceptedException:
                    print("[WARN] Load-more button intercepted — checking for overlays...")
                    # Age dialog may have appeared after initial check
                    try:
                        da_btn = driver.find_element(By.XPATH, "//button[normalize-space()='DA']")
                        da_btn.click()
                        print("[INFO] Age verification dismissed during content loading.")
                        time.sleep(3)
                    except Exception:
                        # Newsletter or other overlay — try scrolling past it
                        driver.execute_script("window.scrollBy(0, 100);")
                        time.sleep(2)
                    attempts += 1
                except Exception as e:
                    print(f"[ERROR] Unexpected error in load_all_content: {type(e).__name__}: {e}")
                    attempts += 1
                    time.sleep(2)

        load_all_content()

        # Scroll from top to bottom slowly so IntersectionObserver fires for every
        # image and Next.js swaps the placeholder src to the real image URL.
        # Scroll from top to bottom so IntersectionObserver fires for each product.
        print("[INFO] Scrolling through page to trigger image lazy loading...")
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        total_height = driver.execute_script("return document.body.scrollHeight")
        step = 600
        pos = 0
        while pos < total_height:
            pos += step
            driver.execute_script(f"window.scrollTo(0, {pos});")
            time.sleep(0.3)
            total_height = driver.execute_script("return document.body.scrollHeight")

        # Poll until all placeholder srcs are replaced with real URLs (max 20s).
        print("[INFO] Waiting for all images to resolve...")
        remaining = 0
        deadline = time.time() + 20
        while time.time() < deadline:
            remaining = driver.execute_script("""
                return Array.from(document.querySelectorAll(
                    'li.sc-5ce8ced0-0.bcCFxH img[data-nimg="fill"]'
                )).filter(img => !img.src.startsWith('http')).length;
            """)
            if remaining == 0:
                break
            time.sleep(0.5)
        if remaining:
            print(f"[WARN] {remaining} images still unresolved after timeout.")

        # Extract image URLs from the live DOM — guaranteed to reflect the current
        # src values (after IntersectionObserver has fired), unlike page_source.
        print("[INFO] Extracting image URLs from live DOM...")
        image_urls = driver.execute_script("""
            return Array.from(document.querySelectorAll('li.sc-5ce8ced0-0.bcCFxH')).map(item => {
                const img = item.querySelector('img[data-nimg="fill"]') || item.querySelector('img');
                if (!img) return null;
                const src = img.src || '';
                return src.startsWith('http') ? src : null;
            });
        """)

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
            size_elem  = item.select_one("span.sc-5ce8ced0-9.QXiqi")
            link_elem  = item.select_one("a")

            # Use live-DOM image URL (indexed by position) — avoids page_source timing issues
            img_url = image_urls[idx] if idx < len(image_urls) else None

            if title_elem and price_elem:
                products.append({
                    "title": title_elem.get_text(strip=True),
                    "price": price_elem.get_text(strip=True),
                    "size":  size_elem.get_text(strip=True) if size_elem else None,
                    "link":  link_elem["href"] if link_elem and "href" in link_elem.attrs else None,
                    "image": img_url,
                })
            else:
                print(f"[WARN] Product {idx + 1}: Missing title or price.")

        with_images = sum(1 for p in products if p.get('image'))
        print(f"[INFO] Extracted {len(products)} products ({with_images} with images, {len(products) - with_images} without).")

        safe_name   = name.replace("/", "-")
        script_dir  = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.normpath(os.path.join(script_dir, "../../data/ecuga", safe_name + "_ecuga.json"))
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Fill missing images from the previous scrape (title → image lookup)
        if os.path.exists(output_path):
            try:
                with open(output_path, encoding="utf-8") as f:
                    prev = json.load(f)
                prev_images = {p["title"]: p["image"] for p in prev if p.get("image")}
                filled = 0
                for p in products:
                    if not p.get("image") and p["title"] in prev_images:
                        p["image"] = prev_images[p["title"]]
                        filled += 1
                if filled:
                    print(f"[INFO] Filled {filled} missing images from previous scrape.")
            except Exception as e:
                print(f"[WARN] Could not load previous scrape for image fallback: {e}")

        print(f"[INFO] Saving {len(products)} products to {output_path}...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)

        print("[INFO] Done!")

    except Exception as e:
        print(f"[ERROR] Something went wrong: {e}", file=sys.stderr)

    finally:
        try:
            driver.quit()
        except Exception:
            pass
