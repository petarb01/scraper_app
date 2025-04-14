import asyncio
import time
from cugaklik_scraper import cugaclick_scraper

async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)

# Main async function to run all scrapers in parallel
async def main():
    start_time = time.time()
    print("[INFO] Starting parallel scraping with Selenium and asyncio...")
    
    # Create tasks for each scraper with their own driver
    tasks = [
        run_in_executor(lambda: cugaclick_scraper("zestoka-cuga")),
        run_in_executor(lambda: cugaclick_scraper("whisky")),
        run_in_executor(lambda: cugaclick_scraper("kokteli-i-miksevi")),
        run_in_executor(lambda: cugaclick_scraper("vino")),
    ]
    
    # Run all tasks concurrently and wait for them to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for result in results:
        if isinstance(result, Exception):
            print(f"[ERROR] A scraper failed with exception: {result}")
        else:
            print(f"[SUCCESS] Completed scraping {result}")
    
    elapsed_time = time.time() - start_time
    print(f"[INFO] All scraping completed in {elapsed_time:.2f} seconds")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())
