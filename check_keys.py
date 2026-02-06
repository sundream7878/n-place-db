import json
import os

regions_file = 'crawler/regions.json'
if os.path.exists(regions_file):
    with open(regions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print("Keys:", list(data.keys()))
else:
    print("File not found")
