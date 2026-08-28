from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import re


BASE_DIR = Path(r"C:\YT-Automation")

ASSET_DIR = BASE_DIR / "assets" / "source"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

MANIFEST = BASE_DIR / "assets" / "asset_manifest.json"

API_URL = "https://commons.wikimedia.org/w/api.php"


def clean_filename(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:100]


def api_request(params: dict) -> dict:
    query = urlencode(params)

    request = Request(
        f"{API_URL}?{query}",
        headers={
            "User-Agent": "YT-Automation-MVP/1.0"
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def search_commons(search_term: str) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": search_term,
        "gsrnamespace": "6",
        "gsrlimit": "5",
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1920",
    }

    return api_request(params)


def get_metadata(page: dict) -> dict:
    info = page["imageinfo"][0]
    metadata = info.get("extmetadata", {})

    def value(name):
        item = metadata.get(name, {})
        return item.get("value", "")

    return {
        "title": page.get("title"),
        "file_url": info.get("url"),
        "description_url": info.get("descriptionurl"),
        "mime": info.get("mime"),
        "width": info.get("width"),
        "height": info.get("height"),
        "author": value("Artist"),
        "license": value("LicenseShortName"),
        "license_url": value("LicenseUrl"),
        "credit": value("Credit"),
    }


def download_file(url: str, output: Path):
    request = Request(
        url,
        headers={
            "User-Agent": "YT-Automation-MVP/1.0"
        },
    )

    with urlopen(request, timeout=60) as response:
        data = response.read()

    output.write_bytes(data)


def main():

    search_term = (
        "artificial intelligence data center server"
    )

    print(f"Searching Wikimedia Commons:")
    print(search_term)

    data = search_commons(search_term)

    pages = list(
        data.get("query", {})
        .get("pages", {})
        .values()
    )

    if not pages:
        raise RuntimeError(
            "No Wikimedia Commons results found."
        )

    print(f"Candidates found: {len(pages)}")

    selected = None

    for page in pages:

        metadata = get_metadata(page)

        print()
        print(metadata["title"])
        print("License:", metadata["license"])
        print("Author:", metadata["author"])

        # For the MVP, accept only files with
        # an explicitly reported license.
        if metadata["license"]:
            selected = metadata
            break

    if not selected:
        raise RuntimeError(
            "No candidate with license metadata found."
        )

    print()
    print("Selected:")
    print(selected["title"])
    print("License:", selected["license"])

    filename = clean_filename(
        selected["title"].replace("File:", "")
    )

    output = ASSET_DIR / filename

    print("Downloading...")
    download_file(
        selected["file_url"],
        output,
    )

    manifest = []

    if MANIFEST.exists():
        manifest = json.loads(
            MANIFEST.read_text(
                encoding="utf-8"
            )
        )

    manifest.append(
        {
            "local_file": str(output),
            "source": "Wikimedia Commons",
            "source_url": selected["description_url"],
            "file_url": selected["file_url"],
            "title": selected["title"],
            "author": selected["author"],
            "license": selected["license"],
            "license_url": selected["license_url"],
            "credit": selected["credit"],
        }
    )

    MANIFEST.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("SUCCESS")
    print("Downloaded:", output)
    print("Manifest:", MANIFEST)


if __name__ == "__main__":
    main()