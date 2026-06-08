import asyncio
import time
from diskontfumar_scraper import diskontfumar_scraper

CATEGORIES = [
    "vodka",
    "gin",
    "whiskey",
    "rum",
    "konjak",
    "rakija",
    "liquer",
    "tequila",
    "sampanjci-i-pjenusci",
    "pivo",
    "vino",
    "kokteli",
]

MAX_CONCURRENT = 4

async def run_with_semaphore(semaphore, name):
    async with semaphore:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, diskontfumar_scraper, name)

async def main():
    start_time = time.time()
    print(f"[INFO] Starting scraping ({MAX_CONCURRENT} browsers at a time)...")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [run_with_semaphore(semaphore, name) for name in CATEGORIES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for name, result in zip(CATEGORIES, results):
        if isinstance(result, Exception):
            print(f"[ERROR] {name}: {result}")
        else:
            print(f"[SUCCESS] {name}")

    elapsed_time = time.time() - start_time
    print(f"[INFO] All scraping completed in {elapsed_time:.2f} seconds")

    return results

if __name__ == "__main__":
    asyncio.run(main())
