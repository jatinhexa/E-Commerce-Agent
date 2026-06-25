import asyncio
import traceback

from app.indexer import sync_all

async def main():
    try:
        print("Starting sync...")
        res = await sync_all()
        print("Sync success:", res)
    except Exception as e:
        print("Sync failed!")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
