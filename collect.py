import requests
import time
import os
import json
import tarfile
import shutil
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DATA_DIR = "paperdata"
STATIONS_JSON = "berlin_stations.json"

CLIENT_ID = os.environ["DB_CLIENT_ID"]
API_KEY = os.environ["DB_API_KEY"]

BASE_URL = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
HEADERS = {
    "DB-Client-Id": CLIENT_ID,
    "DB-Api-Key": API_KEY,
    "accept": "application/xml",
}

TZ = ZoneInfo("Europe/Berlin")
REQUEST_DELAY = 0.5
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

with open(STATIONS_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

eva_list = []
for station in data["result"]:
    for eva in station.get("evaNumbers", []):
        eva_list.append(str(eva["number"]))
eva_list = sorted(set(eva_list))


def now_berlin():
    return datetime.now(TZ)


def fetch(url):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            print(f"  net error {url}: {e}")
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            return r.text
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 5)) + 2 ** attempt
            print(f"  429 rate limited, sleep {wait}s")
            time.sleep(wait)
            continue
        print(f"  HTTP {r.status_code} {url}")
        return None
    return None


def _archive(kind, folder, ts):
    tar_path = f"{BASE_DATA_DIR}/{kind}/{ts}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(folder, arcname=ts)
    shutil.rmtree(folder)


def collect_changes(kind):
    ts = now_berlin().strftime("%Y%m%d_%H%M%S")
    folder = f"{BASE_DATA_DIR}/{kind}/{ts}"
    os.makedirs(folder, exist_ok=True)
    saved = 0
    for eva in eva_list:
        text = fetch(f"{BASE_URL}/{kind}/{eva}")
        if text is not None:
            with open(f"{folder}/{eva}.xml", "w", encoding="utf-8") as f:
                f.write(text)
            saved += 1
        time.sleep(REQUEST_DELAY)
    _archive(kind, folder, ts)
    print(f"{kind} {ts}: saved {saved}/{len(eva_list)}")


def collect_plan():
    now = now_berlin()
    date, hour = now.strftime("%y%m%d"), now.strftime("%H")
    ts = now.strftime("%Y%m%d_%H%M%S")
    folder = f"{BASE_DATA_DIR}/plan/{ts}"
    os.makedirs(folder, exist_ok=True)
    saved = 0
    for eva in eva_list:
        text = fetch(f"{BASE_URL}/plan/{eva}/{date}/{hour}")
        if text is not None:
            with open(f"{folder}/{eva}.xml", "w", encoding="utf-8") as f:
                f.write(text)
            saved += 1
        time.sleep(REQUEST_DELAY)
    _archive("plan", folder, ts)
    print(f"plan {ts}: saved {saved}/{len(eva_list)}  (hour={hour})")


for kind in ("fchg", "rchg", "plan"):
    os.makedirs(f"{BASE_DATA_DIR}/{kind}", exist_ok=True)

mode = sys.argv[1] if len(sys.argv) > 1 else "rchg"

if mode == "plan":
    collect_plan()
elif mode == "fchg":
    collect_changes("fchg")
else:  # rchg
    collect_changes("rchg")