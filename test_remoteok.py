import asyncio
import json

from scrapers.sources.remoteok import RemoteOKScraper


async def main():
    s = RemoteOKScraper(limit=2)
    await s.search('python')
    jobs = await s.extract_jobs()
    norm = []
    for j in jobs:
        norm.append(await s.normalize(j))
    print(json.dumps(norm, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
