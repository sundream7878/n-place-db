import requests
import config
import time
from geopy.geocoders import ArcGIS
from geopy.exc import GeocoderTimedOut

def geocode_bupyeong():
    url = config.SUPABASE_URL
    key = config.SUPABASE_KEY
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    # Precise center of Bupyeong-dong from previous Nominatim run
    center_lat = 37.4906976
    
    # 1. Fetch shops in Bupyeong-dong with 0 coords or center coords
    query_url = f"{url}/rest/v1/t_crawled_shops?address=ilike.*부평동*&or=(latitude.eq.0,latitude.eq.{center_lat})&select=id,name,address"
    resp = requests.get(query_url, headers=headers)
    
    if resp.status_code != 200:
        print(f"[-] Failed to fetch shops: {resp.status_code} {resp.text}")
        return
    
    shops = resp.json()
    print(f"[*] Found {len(shops)} shops in Bupyeong-dong to geocode.")
    
    geolocator = ArcGIS()
    
    for shop in shops:
        shop_id = shop['id']
        name = shop['name']
        address = shop['address']
        
        print(f"[*] Geocoding [{name}]: {address}")
        
        try:
            location = geolocator.geocode(address)
            
            if location:
                print(f"    [+] Found: {location.latitude}, {location.longitude}")
                
                # Update DB
                update_data = {
                    "latitude": location.latitude,
                    "longitude": location.longitude
                }
                update_url = f"{url}/rest/v1/t_crawled_shops?id=eq.{shop_id}"
                upd_resp = requests.patch(update_url, headers=headers, json=update_data)
                
                if upd_resp.status_code in [200, 204]:
                    print(f"    [+] DB Updated.")
                else:
                    print(f"    [-] DB Update Failed: {upd_resp.status_code}")
            else:
                print(f"    [-] Geocoding failed for {address}")
                
            # ArcGIS rate limit is generous but let's be polite
            time.sleep(0.5)
            
        except GeocoderTimedOut:
            print(f"    [!] Timeout geocoding {name}. Skipping...")
            continue
        except Exception as e:
            print(f"    [!] Error geocoding {name}: {e}")
            continue

if __name__ == "__main__":
    geocode_bupyeong()
