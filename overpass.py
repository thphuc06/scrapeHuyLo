# -*- coding: utf-8 -*-
"""
Thu thập địa điểm du lịch OSM - PHIÊN BẢN OVERPASS/NOMINATIM (TINH LỌC DU LỊCH)
- CHỈ tập trung vào ngắm cảnh, tham quan, giải trí cốt lõi.
- Đã loại bỏ các tags: accommodation, commercial, catering.
"""

import requests
import csv
import time
import re
import math
import json
from typing import List, Dict, Optional, Tuple

# ============================================================
# CẤU HÌNH API
# ============================================================
# Overpass API mặc định (ổn định)
OVERPASS_URL = "https://overpass-api.de/api/interpreter" 
# Nominatim API (để lấy BBox)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Email liên hệ, quan trọng khi dùng Nominatim và Overpass
# HÃY DÙNG EMAIL THẬT CỦA BẠN!
USER_AGENT_CONTACT = "OSMDataScraperVietNam/1.0 (phuctran180406@gmail.com)" 

# ============================================================
# ÁNH XẠ GEOAPIFY CATEGORIES SANG OSM TAGS (TINH LỌC DU LỊCH CỐT LÕI)
# ============================================================
OSM_TAGS_MAP = {
    # Du lịch cốt lõi / Historic / Điểm tham quan
    "tourism_core": [
        "tourism=attraction", "tourism=viewpoint", "tourism=museum", 
        "tourism=artwork", "tourism=theme_park", "tourism=gallery",
        "tourism=zoo", "tourism=aquarium", "historic", "amenity=theatre"
    ],
    
    # Chùa, Nhà thờ, Tôn giáo (Văn hóa)
    "worship": ["amenity=place_of_worship"],
    
    # Thiên nhiên & Giải trí (Công viên, Bãi biển, Núi non, Resort)
    "natural_leisure": [
        "natural", "natural=peak", "natural=cave_entrance", "natural=bay",
        "leisure=park", "leisure=garden", "leisure=golf_course",
        "leisure=beach", "natural=wood", "leisure=resort"
    ],
    
    # Giao thông quan trọng (Cửa ngõ du lịch)
    "transport": [
        "aeroway=airport", "railway=station", "amenity=ferry_terminal" 
    ]
}

def get_city_bbox(city_name: str) -> Optional[List[float]]:
    """Lấy khung bao (BBox) của thành phố bằng Nominatim."""
    url = NOMINATIM_URL
    params = {
        "q": city_name, 
        "format": "json", 
        "limit": 1, 
        "addressdetails": 0,
        "email": USER_AGENT_CONTACT.split('(')[-1].replace(')', '')
    }
    headers = {'User-Agent': USER_AGENT_CONTACT}
    
    print("   ⏳ Đang gọi Nominatim...")
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        
        if resp.status_code != 200:
            print(f"❌ Lỗi HTTP {resp.status_code} từ Nominatim.")
            print(f"   Nội dung phản hồi: {resp.text[:200]}...")
            return None
        
        try:
            data = resp.json()
        except json.JSONDecodeError:
            print("❌ Lỗi JSONDecodeError.")
            print(f"   Nominatim không trả về JSON hợp lệ. Nội dung thô: {resp.text[:200]}...")
            return None
            
        if data and data[0].get("boundingbox"):
            # Bounding box từ Nominatim là [min_lat, max_lat, min_lon, max_lon]
            bb = data[0]["boundingbox"]
            # Trả về định dạng [min_lon, min_lat, max_lon, max_lat]
            return [float(bb[2]), float(bb[0]), float(bb[3]), float(bb[1])]
    except Exception as e:
        print(f"❌ Lỗi kết nối hoặc yêu cầu chung: {e}")
    return None

def build_overpass_query(bbox: List[float]) -> str:
    """
    Tạo truy vấn Overpass QL để lấy các POI trong BBox.
    Format BBox: (min_lat, min_lon, max_lat, max_lon)
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    overpass_bbox = f"({min_lat},{min_lon},{max_lat},{max_lon})"
    
    query_parts = []
    for category, tags in OSM_TAGS_MAP.items():
        for tag in tags:
            if "=" in tag:
                key, val = tag.split('=', 1)
                # Lấy nodes, ways, và relations thỏa mãn tag trong BBox
                query_parts.append(f'  (node[{key}="{val}"]{overpass_bbox};')
                query_parts.append(f'   way[{key}="{val}"]{overpass_bbox};')
                query_parts.append(f'   relation[{key}="{val}"]{overpass_bbox};);')
            else:
                # Lấy nodes, ways, và relations thỏa mãn key (bất kể giá trị)
                query_parts.append(f'  (node["{tag}"]{overpass_bbox};')
                query_parts.append(f'   way["{tag}"]{overpass_bbox};')
                query_parts.append(f'   relation["{tag}"]{overpass_bbox};);')
                
    # Kết hợp các truy vấn vào một khối (union)
    query = f"[out:json][timeout:120];\n(\n"
    query += '\n'.join(query_parts)
    query += "\n);\nout center;\n" # output center of ways/relations
    return query

def fetch_places_from_overpass(query: str) -> List[Dict]:
    """Thực hiện truy vấn Overpass và trích xuất kết quả."""
    headers = {'User-Agent': USER_AGENT_CONTACT}
    
    try:
        resp = requests.post(OVERPASS_URL, data={'data': query}, headers=headers, timeout=120)
        if resp.status_code != 200:
            print(f"❌ Lỗi Overpass (Status {resp.status_code}): {resp.text[:100]}...")
            return []
        
        elements = resp.json().get("elements", [])
        
        places = []
        for elem in elements:
            props = elem.get("tags", {})
            
            # Lấy tên (name)
            name = props.get("name", "").strip()
            
            # Lấy tọa độ (Node: trực tiếp, Way/Relation: từ center)
            lat = elem.get("lat") or elem.get("center", {}).get("lat")
            lon = elem.get("lon") or elem.get("center", {}).get("lon")
            
            # Lấy địa chỉ (từ address:street, house_number, city...)
            address = props.get("addr:full") or props.get("addr:street", "")
            if props.get("addr:housenumber"):
                address = f"{props.get('addr:housenumber')} {address}"
                
            # Lấy loại hình (type) - Lấy tag có giá trị phổ biến nhất
            place_type = "unknown"
            if props.get("tourism"): place_type = props["tourism"]
            elif props.get("shop"): place_type = props["shop"]
            elif props.get("leisure"): place_type = props["leisure"]
            elif props.get("amenity"): place_type = props["amenity"]
            elif props.get("natural"): place_type = props["natural"]
            elif props.get("historic"): place_type = props["historic"]
            
            if is_valid_place(name, place_type) and lat and lon:
                places.append({
                    "id": f"OSM-{elem['type']}-{elem['id']}",
                    "name": name,
                    "type": place_type,
                    "address": address.strip(),
                    "lat": lat,
                    "lon": lon
                })

        return places
    except Exception as e:
        print(f"❌ Lỗi truy vấn Overpass: {e}")
        return []

def is_valid_place(name: str, type_val: str) -> bool:
    """Bộ lọc rác (Tối ưu để loại bỏ Khách sạn, Ăn uống, Dịch vụ phụ trợ)"""
    if not name or len(name) <= 2: return False
    name_lower = name.lower().strip()
    
    # 1. Lọc tên là địa chỉ (Rất quan trọng)
    if re.search(r'^(kiệt|hẻm|ngõ|đường|số|tổ)\s+\d+', name_lower): return False
    if re.search(r'^(đối diện|bên cạnh)', name_lower): return False

    # 2. Lọc loại hình rác & Phụ trợ (Chỗ ở, Ăn uống, Dịch vụ, Thể thao)
    junk_types_and_services = [
        'residential', 'parking', 'toilet', 'private', 'apartments', 'office', 
        'estate_agent', 'yes', 'no', 'information', 'bus_station', 'marina',
        'station', 'camp_site', 'sauna', 'unknown',
        
        # Loại bỏ chỗ ở:
        'hotel', 'hostel', 'motel', 'guest_house', 'apartment',
        
        # Loại bỏ ăn uống:
        'restaurant', 'cafe', 'fast_food', 'pub', 'bar', 'biergarten', 
        
        # Loại bỏ thương mại, thể thao, dịch vụ địa phương:
        'shop', 'market', 'mall', 'pitch', 'stadium', 'sports_centre', 
        'sports_hall', 'fitness_centre', 'cemetery', 'kindergarten'
    ]
    
    # Giữ lại 'resort', 'park', 'attraction' và các POI cốt lõi
    if type_val in junk_types_and_services: return False
    
    # 3. Lọc từ khóa rác
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
    print("="*60 + "\n🗺️  OSM OVERPASS SCAN (TINH LỌC DU LỊCH)\n" + "="*60)
    
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
    
    # BƯỚC 1: Lấy khung bao thành phố (Nominatim)
    print(f"\n1️⃣  Đang lấy khung bao cho: {selected_name}...")
    bbox = get_city_bbox(selected_name)
    if not bbox: return
    print(f"   📐 BBox: {bbox}")
    
    # BƯỚC 2: Xây dựng truy vấn Overpass QL
    print(f"2️⃣  Đang xây dựng truy vấn Overpass...")
    query = build_overpass_query(bbox)
    # print("--- QUERY SAMPLE ---")
    # print(query[:500] + "...")
    # print("--------------------")

    # BƯỚC 3: Thực hiện truy vấn và quét POI
    print(f"3️⃣  Bắt đầu quét Overpass (Quá trình này có thể mất 1-2 phút). Vui lòng chờ...")
    all_results = fetch_places_from_overpass(query)
        
    print(f"\n\n✅ HOÀN TẤT QUÉT! Đã tìm thấy: {len(all_results)} địa điểm")
    export_to_csv(all_results, f"{safe_name}_osm_core_data.csv")

if __name__ == "__main__":
    main()