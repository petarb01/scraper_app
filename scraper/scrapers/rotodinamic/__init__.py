import asyncio
import time
from rotodinamic_scraper import rotodinamic_scraper

CATEGORIES = [
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Rum",
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Brandy",
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Tequila",
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Koktel,Koktel miks",
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Gin",
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Liker",
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Rakija",
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Vodka",
    "jaka-alkoholna-pica/filter/19-vrsta-jap,Viski,Whiskey,Whisky",
    "pivo",
    "vino",
]

MAX_CONCURRENT = 4

async def run_with_semaphore(semaphore, name):
    async with semaphore:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, rotodinamic_scraper, name)

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
