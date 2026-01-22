import argparse
import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from app.main import extract_full_text


async def run(urls):
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            text = await extract_full_text(url)
            print(f"{url} -> {len(text)} chars")
        except Exception as exc:
            print(f"{url} -> error: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Smoke-test full text extraction for URLs.")
    parser.add_argument("url_file", help="Path to a newline-delimited URL file.")
    args = parser.parse_args()

    with open(args.url_file, "r", encoding="utf-8") as handle:
        urls = handle.readlines()

    asyncio.run(run(urls))


if __name__ == "__main__":
    main()
