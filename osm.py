# -*- coding: utf-8 -*-
"""
Thu thập địa điểm du lịch Geoapify - PHIÊN BẢN GRID SCAN (FULL CATEGORIES)
- Quét lưới toàn thành phố.
- Bổ sung: Khách sạn, Chợ, Mall, Quà lưu niệm, Sân bay, Ga tàu.
"""

import requests
import csv
import time
import re
import math
from typing import List, Dict

# ============================================================
# CẤU HÌNH API KEY
# ============================================================
GEOAPIFY_API_KEY = "9356d5c507ed489c8bf5c7aee3ab48ad" 

def get_city_bbox(city_name: str) -> List[float]:
    """Lấy khung bao (BBox) của thành phố."""
    url = "https://api.geoapify.com/v1/geocode/search"
    params = {"text": city_name, "apiKey": GEOAPIFY_API_KEY, "limit": 1, "lang": "vi"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("features"):
            bbox = data["features"][0].get("bbox")
            if bbox: return bbox
            # Fallback
            props = data["features"][0]["properties"]
            lat, lon = props.get("lat"), props.get("lon")
            return [lon - 0.1, lat - 0.1, lon + 0.1, lat + 0.1]
    except Exception as e:
        print(f"❌ Lỗi lấy BBox: {e}")
    return None

def generate_grid(bbox: List[float], step_km: float = 5.0) -> List[str]:
    """Chia BBox lớn thành lưới nhỏ."""
    min_lon, min_lat, max_lon, max_lat = bbox
    step_lat = step_km / 111.0
    step_lon = step_km / (111.0 * math.cos(math.radians((min_lat + max_lat)/2)))
    
    grids = []
    curr_lon = min_lon
    while curr_lon < max_lon:
        curr_lat = min_lat
        while curr_lat < max_lat:
            next_lon = min(curr_lon + step_lon, max_lon)
            next_lat = min(curr_lat + step_lat, max_lat)
            rect_str = f"{curr_lon},{curr_lat},{next_lon},{next_lat}"
            grids.append(rect_str)
            curr_lat += step_lat
        curr_lon += step_lon
    return grids

def fetch_places_from_rect(rect_str: str) -> List[Dict]:
    """Quét địa điểm trong 1 ô vuông nhỏ"""
    url = "https://api.geoapify.com/v2/places"
    
    # [DANH SÁCH CATEGORIES MỞ RỘNG]
    categories = (
        "tourism,"                  # Du lịch chung
        "entertainment,"            # Giải trí (Zoo, Aquarium...)
        "building.historic,"        # Di tích
        "building.place_of_worship,"# Chùa, Nhà thờ
        "natural,"                  # Thiên nhiên (Biển, Núi)
        "leisure,"                  # Công viên, Resort
        "commercial.marketplace,"   # [MỚI] Chợ truyền thống
        "commercial.gift_and_souvenir," # [MỚI] Quà lưu niệm
    )
    
    places = []
    offset = 0
    limit = 100 
    
    while True:
        params = {
            "categories": categories,
            "filter": f"rect:{rect_str}",
            "limit": limit,
            "offset": offset,
            "apiKey": GEOAPIFY_API_KEY,
            "lang": "vi"
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200: break
            features = resp.json().get("features", [])
            if not features: break
            
            for f in features:
                props = f["properties"]
                name = props.get("name", "").strip()
                address = props.get("formatted", "")
                
                cats = props.get("categories", [])
                raw_type = cats[-1] if cats else "unknown"
                place_type = raw_type.split('.')[-1]
                
                if is_valid_place(name, place_type):
                    places.append({
                        "id": props.get("place_id", "")[-10:],
                        "name": name,
                        "type": place_type,
                        "address": address,
                        "lat": props.get("lat"),
                        "lon": props.get("lon")
                    })
            
            offset += limit
            if len(features) < limit: break
        except: break
        
    return places

def is_valid_place(name: str, type_val: str) -> bool:
    """Bộ lọc rác (Đã nâng cấp cho accommodation và commercial)"""
    if not name or len(name) <= 2: return False
    name_lower = name.lower().strip()
    
    # 1. Lọc tên là địa chỉ (Vẫn giữ vì rất quan trọng)
    if re.search(r'^(kiệt|hẻm|ngõ|đường|số|tổ)\s+\d+', name_lower): return False
    if re.search(r'^(đối diện|bên cạnh)', name_lower): return False

    # 2. Lọc loại hình rác
    # 'motel': Tùy bạn, thường motel ở VN là nhà nghỉ bình dân, có thể lọc nếu muốn app sang chảnh
    junk_types = ['residential', 'parking', 'toilet', 'private', 'apartments', 'office', 'estate_agent']
    if type_val in junk_types: return False

    # 3. Lọc từ khóa rác
    # Giữ lại 'shop', 'store' vì giờ ta lấy cả Shopping Mall và Souvenir
    junk_keywords = [
        'atm ', 'ngân hàng', 'lốp xe', 'sửa xe', 'thcs', 'thpt', 'mầm non', 
        'nhà tui', 'my house', 'bất động sản', 'internet', 'game'
    ]
    
    if any(j in name_lower for j in junk_keywords): return False
    return True

def export_to_csv(places: List[Dict], filename: str):
    if not places: return
    # Lọc trùng ID
    unique = {p['id']: p for p in places}.values()
    
    fieldnames = ['id', 'name', 'type', 'address', 'lat', 'lon']
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(unique)
        print(f"\n💾 Đã lưu {len(unique)} địa điểm duy nhất vào: {filename}")
    except Exception as e: print(f"❌ Lỗi lưu file: {e}")

# ============================================================
# MAIN
# ============================================================
CITIES = {
    "Thành phố Đà Nẵng": "Da_Nang",
    "Thành phố Hà Nội": "Ha_Noi",
    "Thành phố Hồ Chí Minh": "Ho_Chi_Minh",
    "Thành phố Hội An": "Hoi_An",
    "Thành phố Huế": "Hue",
    "Thành phố Đà Lạt": "Da_Lat",
    "Thành phố Nha Trang": "Nha_Trang",
    "Thị xã Sa Pa": "Sa_Pa",
    "Thành phố Vũng Tàu": "Vung_Tau",
    "Thành phố Cần Thơ": "Can_Tho",
    "Thành phố Hải Phòng": "Hai_Phong"
}

def main():
    print("="*60 + "\n🗺️  GEOAPIFY GRID SCAN (FULL DATA)\n" + "="*60)
    
    if "YOUR_GEOAPIFY_API_KEY" in GEOAPIFY_API_KEY:
        print("❌ LỖI: Chưa nhập API Key!")
        return

    locs = list(CITIES.keys())
    for i, loc in enumerate(locs, 1): print(f"{i}. {loc}")
    
    inp = input("\n>>> Chọn số hoặc nhập tên thành phố: ").strip()
    if inp.isdigit() and 1 <= int(inp) <= len(locs):
        selected_name = locs[int(inp)-1]
    elif inp in CITIES:
        selected_name = inp
    else:
        print("⚠️ Mặc định chọn Đà Nẵng")
        selected_name = "Thành phố Đà Nẵng"
    
    safe_name = CITIES.get(selected_name, "output")
    
    # BƯỚC 1: Lấy khung bao thành phố
    print(f"\n1️⃣  Đang lấy khung bao cho: {selected_name}...")
    bbox = get_city_bbox(selected_name)
    if not bbox: return
    print(f"   📐 BBox: {bbox}")
    
    # BƯỚC 2: Chia lưới (Mỗi ô 5km)
    print(f"2️⃣  Đang chia lưới (Grid)...")
    grids = generate_grid(bbox, step_km=5.0)
    print(f"   田 Tổng cộng: {len(grids)} ô lưới cần quét.")
    
    # BƯỚC 3: Quét từng ô
    print(f"3️⃣  Bắt đầu quét (Full Categories)...")
    all_results = []
    
    for i, rect in enumerate(grids, 1):
        print(f"\r   ⏳ Đang quét ô {i}/{len(grids)}... (Đã tìm thấy: {len(all_results)})", end="")
        results = fetch_places_from_rect(rect)
        all_results.extend(results)
        time.sleep(0.1) # Geoapify chịu tải tốt, delay 0.1s là đủ
        
    print(f"\n\n✅ HOÀN TẤT QUÉT!")
    export_to_csv(all_results, f"{safe_name}_full_data.csv")

if __name__ == "__main__":
    main()