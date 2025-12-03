# -*- coding: utf-8 -*-
"""
Thu thập địa điểm du lịch ngắm cảnh tại Việt Nam - VERSION 2 OPTIMIZED
- Tập trung vào điểm ngắm cảnh, khu du lịch
- Bỏ categories gây noise
- Tăng coverage cho categories quan trọng
"""

import requests
import csv
import json
import sys
import time
from typing import List, Dict

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
API_KEY = "584f7d13c17646447813d8a999dfc60ec2"
BASE_URL = "https://maps.track-asia.com/api/v2/place/autocomplete/json"

# ============================================================================
# TOURIST CATEGORIES - OPTIMIZED
# ============================================================================
# Nguyên tắc:
# 1. Ưu tiên categories ngắm cảnh, du lịch (nhiều keywords hơn)
# 2. Bỏ categories hiếm/gây noise
# 3. Keywords phải specific, tránh match sai
# ============================================================================

TOURIST_CATEGORIES = {
    # ===========================================
    # TIER 1: ƯU TIÊN CAO - Điểm ngắm cảnh & Du lịch (nhiều keywords)
    # ===========================================
    "Khu du lịch": [
        "khu du lịch", "resort", "khu nghỉ dưỡng", "du lịch sinh thái",
        "tourism", "tourist attraction", "điểm du lịch",
        "khu giải trí", "làng du lịch", "farmstay"
    ],
    
    "Điểm tham quan": [
        "điểm tham quan", "thắng cảnh", "địa danh nổi tiếng", "danh lam",
        "điểm check-in", "viewpoint", "điểm ngắm cảnh", "panorama",
        "ngắm hoàng hôn", "sunrise point", "sunset point", "sky view",
        "observation deck", "đài quan sát", "tháp ngắm cảnh"
    ],
    
    "Bãi biển": [
        "bãi biển", "beach", "bờ biển", "bãi tắm", "vịnh",
        "bãi cát", "lagoon", "đầm", "cửa biển", "bãi biển đẹp",
        "bãi biển hoang sơ", "coastal", "seaside", "ocean view"
    ],
    
    "Công viên": [
        "công viên", "park", "vườn hoa", "công viên sinh thái",
        "công viên cây xanh", "garden", "botanical garden", "vườn bách thảo",
        "công viên ven sông", "công viên biển", "quảng trường"
    ],
    
    # ===========================================
    # TIER 2: TRUNG BÌNH - Thiên nhiên
    # ===========================================
    "Núi & Đèo": [
        "núi", "đỉnh núi", "leo núi", "đèo", "mountain",
        "đồi", "cao nguyên", "núi lửa", "núi đá", "peak",
        "trekking", "hiking trail", "đường mòn"
    ],
    
    "Hồ & Sông": [
        "hồ nước ngọt", "hồ du lịch", "hồ nhân tạo", "hồ tự nhiên",
        "lake", "đập nước", "hồ thủy điện", "hồ sinh thái",
        "sông", "river cruise", "du thuyền sông"
    ],
    
    "Thác nước": [
        "thác nước", "thác", "waterfall", "suối", "stream",
        "thác đẹp", "cascade", "suối nước nóng", "hot spring"
    ],
    
    "Đảo": [
        "đảo", "quần đảo", "hòn đảo", "island", "hòn",
        "cù lao", "đảo hoang", "đảo du lịch", "archipelago"
    ],
    
    "Hang động": [
        "hang động", "động", "cave", "grotto", "hang",
        "động thiên nhiên", "hang karst", "động đá vôi"
    ],
    
    "Vườn quốc gia": [
        "vườn quốc gia", "national park", "khu bảo tồn",
        "rừng nguyên sinh", "rừng quốc gia", "nature reserve",
        "khu dự trữ sinh quyển", "wildlife sanctuary"
    ],
    
    # ===========================================
    # TIER 3: VĂN HÓA & LỊCH SỬ (ít keywords hơn, tập trung)
    # ===========================================
    "Di tích lịch sử": [
        "di tích lịch sử", "di sản", "heritage", "monument",
        "tượng đài", "thành cổ", "hoàng thành", "cổng thành",
        "di tích quốc gia", "historical site"
    ],
    
    "Chùa & Đền": [
        "chùa", "pagoda", "temple", "đền", "thiền viện",
        "chùa cổ", "chùa lớn", "đền thờ", "miếu"
    ],
    
    "Nhà thờ": [
        "nhà thờ", "church", "cathedral", "thánh đường",
        "nhà thờ cổ", "nhà thờ đá", "nhà thờ lớn"
    ],
    
    "Bảo tàng": [
        "bảo tàng", "museum", "nhà trưng bày", "gallery",
        "bảo tàng lịch sử", "bảo tàng nghệ thuật"
    ],
    
    # ===========================================
    # TIER 4: GIẢI TRÍ & ĐẶC BIỆT
    # ===========================================
    "Công viên giải trí": [
        "công viên giải trí", "theme park", "amusement park",
        "công viên nước", "water park", "khu vui chơi",
        "vinwonders", "sun world", "asia park"
    ],
    
    "Phố cổ & Làng cổ": [
        "phố cổ", "old town", "khu phố cổ", "phố đi bộ",
        "làng cổ", "ancient village", "làng nghề"
    ],
    
    "Chợ đặc sản": [
        "chợ", "chợ đêm", "night market", "chợ nổi",
        "floating market", "chợ hải sản", "chợ địa phương"
    ],
    
    "Cafe ngắm cảnh": [
        "cafe view đẹp", "cafe ngắm cảnh", "rooftop cafe",
        "sky bar", "cafe biển", "cafe núi", "cafe view"
    ],
    
    "Vườn thú & Thủy cung": [
        "vườn thú", "zoo", "thảo cầm viên", "safari",
        "thủy cung", "aquarium", "vinpearl safari"
    ],
}

# Weight cho mỗi tier (số lần search lặp lại)
TIER_WEIGHTS = {
    "Khu du lịch": 3,           # Search 3 lần với variations
    "Điểm tham quan": 3,
    "Bãi biển": 2,
    "Công viên": 2,
    "Núi & Đèo": 1,
    "Hồ & Sông": 1,
    "Thác nước": 1,
    "Đảo": 2,                   # Tăng cho vùng biển
    "Hang động": 1,
    "Vườn quốc gia": 1,
    "Di tích lịch sử": 1,
    "Chùa & Đền": 1,
    "Nhà thờ": 1,
    "Bảo tàng": 1,
    "Công viên giải trí": 1,
    "Phố cổ & Làng cổ": 1,
    "Chợ đặc sản": 1,
    "Cafe ngắm cảnh": 1,
    "Vườn thú & Thủy cung": 1,
}

# Số lượng địa điểm target cho mỗi tỉnh/thành phố
CITY_TARGET_COUNTS = {
    # Miền Bắc - Điểm đến du lịch lớn
    "Hà Nội": 800,
    "Hạ Long": 700,
    "Quảng Ninh": 700,
    "Sapa": 700,
    "Ninh Bình": 700,
    "Hải Phòng": 600,
    
    # Miền Trung - Điểm đến du lịch lớn
    "Đà Nẵng": 800,
    "Huế": 700,
    "Hội An": 700,
    "Nha Trang": 800,
    "Đà Lạt": 800,
    "Quảng Bình": 700,
    "Phú Yên": 600,
    "Quy Nhơn": 550,
    "Phan Thiết": 600,
    
    # Miền Nam - Điểm đến du lịch lớn
    "Thành phố Hồ Chí Minh": 800,
    "Vũng Tàu": 700,
    "Bà Rịa - Vũng Tàu": 650,
    "Phú Quốc": 800,
    "Cần Thơ": 600,
    
    # Mặc định cho các tỉnh khác
    "_default": 400,
}

# Variations cho city name để tăng coverage
CITY_VARIATIONS = {
    "Hà Nội": ["Hà Nội", "Hanoi", "Ba Vì", "Sóc Sơn", "Đông Anh"],
    "Thành phố Hồ Chí Minh": ["TP HCM", "Sài Gòn", "Hồ Chí Minh", "Saigon", "Củ Chi", "Cần Giờ"],
    "Đà Nẵng": ["Đà Nẵng", "Da Nang", "Bà Nà", "Sơn Trà", "Ngũ Hành Sơn"],
    "Nha Trang": ["Nha Trang", "Khánh Hòa", "Cam Ranh", "Vịnh Nha Trang"],
    "Đà Lạt": ["Đà Lạt", "Dalat", "Lâm Đồng", "Langbiang"],
    "Phú Quốc": ["Phú Quốc", "Phu Quoc", "đảo Phú Quốc", "Kiên Giang"],
    "Hạ Long": ["Hạ Long", "Vịnh Hạ Long", "Ha Long Bay", "Quảng Ninh"],
    "Sapa": ["Sapa", "Sa Pa", "Lào Cai", "Fansipan"],
    "Hội An": ["Hội An", "Hoi An", "phố cổ Hội An"],
    "Huế": ["Huế", "Hue", "cố đô Huế", "Thừa Thiên Huế"],
}


class TouristPlaceCollector:
    """Class thu thập địa điểm du lịch - VERSION 2"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.collected_places = {}

    def search_places(self, query: str, limit: int = 20) -> List[Dict]:
        """Tìm kiếm địa điểm"""
        params = {
            "input": query,
            "key": self.api_key,
            "size": limit
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'OK':
                return data.get('predictions', [])
            return []

        except Exception as e:
            print(f"   ⚠️  Lỗi khi tìm '{query[:30]}...': {str(e)[:30]}")
            return []

    def geocode_address(self, address: str) -> tuple:
        """Lấy tọa độ từ địa chỉ"""
        geocode_url = "https://maps.track-asia.com/api/v2/geocode/json"

        params = {
            "address": address,
            "key": self.api_key
        }

        try:
            response = requests.get(geocode_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'OK' and data.get('results'):
                location = data['results'][0].get('geometry', {}).get('location', {})
                return (location.get('lat'), location.get('lng'))
            return (None, None)

        except Exception:
            return (None, None)

    def collect_for_city(self, city_name: str, target_count: int = None) -> List[Dict]:
        """Thu thập địa điểm cho một thành phố với optimization"""
        
        if target_count is None:
            target_count = CITY_TARGET_COUNTS.get(city_name, CITY_TARGET_COUNTS["_default"])
        
        print(f"\n{'=' * 80}")
        print(f"🏙️  THU THẬP DỮ LIỆU: {city_name.upper()}")
        print(f"🎯 Mục tiêu: {target_count} địa điểm")
        print(f"{'=' * 80}\n")

        self.collected_places = {}
        places = []
        
        # Lấy city variations
        city_vars = CITY_VARIATIONS.get(city_name, [city_name])

        # Thử với từng category (theo thứ tự priority)
        for category_name, search_terms in TOURIST_CATEGORIES.items():
            if len(places) >= target_count:
                print(f"\n✅ Đã đạt {target_count} địa điểm! Dừng thu thập.")
                break

            weight = TIER_WEIGHTS.get(category_name, 1)
            print(f"\n📂 Category: {category_name} (weight: {weight}x)")

            # Lặp theo weight
            for _ in range(weight):
                for term in search_terms:
                    if len(places) >= target_count:
                        break

                    # Thử với từng variation của city
                    for city_var in city_vars:
                        if len(places) >= target_count:
                            break
                            
                        query = f"{term} {city_var}"
                        print(f"   🔍 '{query[:50]}'...", end=" ")

                        results = self.search_places(query, limit=20)

                        new_count = 0
                        for pred in results:
                            place_id = pred.get('place_id')

                            if place_id and place_id not in self.collected_places:
                                address = pred.get('description', '')
                                lat, lon = self.geocode_address(address)

                                if lat and lon:
                                    place_data = {
                                        'place_id': place_id,
                                        'name': pred.get('name', ''),
                                        'address': address,
                                        'lat': lat,
                                        'lon': lon,
                                        'type': category_name,
                                    }

                                    self.collected_places[place_id] = place_data
                                    places.append(place_data)
                                    new_count += 1

                                time.sleep(0.1)

                        print(f"➕ {new_count} (Total: {len(places)})")
                        time.sleep(0.2)
                        
                        # Chỉ thử variation đầu tiên nếu đã có kết quả
                        if new_count > 0:
                            break

        print(f"\n{'=' * 80}")
        print(f"✅ Hoàn tất: {len(places)} địa điểm cho {city_name}")
        print(f"{'=' * 80}\n")

        return places

    def export_to_csv(self, places: List[Dict], filename: str):
        """Xuất dữ liệu ra CSV"""
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'place_id', 'name', 'address', 'lat', 'lon', 'type'
                ])
                writer.writeheader()
                for place in places:
                    writer.writerow(place)

            print(f"💾 Đã lưu {len(places)} địa điểm vào: {filename}")
            return True

        except Exception as e:
            print(f"❌ Lỗi khi lưu CSV: {e}")
            return False

    def print_statistics(self, places: List[Dict]):
        """In thống kê"""
        print(f"\n{'=' * 80}")
        print("📊 THỐNG KÊ THEO CATEGORY")
        print(f"{'=' * 80}\n")

        category_count = {}
        for place in places:
            cat = place['type']
            category_count[cat] = category_count.get(cat, 0) + 1

        sorted_cats = sorted(category_count.items(), key=lambda x: x[1], reverse=True)

        for cat, count in sorted_cats:
            bar = "█" * min(50, count // 2)
            print(f"  {cat:<25} {count:>4} {bar}")

        print(f"\n  {'TỔNG CỘNG':<25} {len(places):>4}")
        print(f"{'=' * 80}\n")


def main():
    """Hàm chính"""
    collector = TouristPlaceCollector(API_KEY)

    cities = [
        # Top destinations
        "Hà Nội", "Thành phố Hồ Chí Minh", "Đà Nẵng",
        "Nha Trang", "Đà Lạt", "Phú Quốc",
        "Hạ Long", "Sapa", "Hội An", "Huế",
        # More cities...
    ]

    print("=" * 80)
    print("🗺️  THU THẬP ĐỊA ĐIỂM DU LỊCH VIỆT NAM - V2 OPTIMIZED")
    print("=" * 80)
    
    print(f"\n📋 Danh sách thành phố:")
    for idx, city in enumerate(cities, 1):
        print(f"   {idx}. {city}")

    print(f"\nNhập số thứ tự (hoặc 'all'):")
    user_input = input(">>> ").strip()

    if user_input.lower() == 'all':
        selected_cities = cities
    elif user_input.isdigit() and 1 <= int(user_input) <= len(cities):
        selected_cities = [cities[int(user_input) - 1]]
    else:
        selected_cities = ["Đà Nẵng"]  # Default

    for city in selected_cities:
        places = collector.collect_for_city(city)
        
        safe_name = city.replace(" ", "_")
        collector.export_to_csv(places, f"{safe_name}_tourist_places.csv")
        
        with open(f"{safe_name}_tourist_places.json", 'w', encoding='utf-8') as f:
            json.dump(places, f, ensure_ascii=False, indent=2)
        
        collector.print_statistics(places)

    print("\n✅ HOÀN TẤT!")


if __name__ == "__main__":
    main()