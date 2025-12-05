# Danh sách tỉnh thành du lịch Việt Nam

## Tier 1 - Nhiều địa điểm nhất (ưu tiên scrape trước)

| STT | Tỉnh/Thành phố | City fallback | Đặc điểm nổi bật |
|-----|----------------|---------------|------------------|
| 1 | Hà Nội | Hà Nội, Việt Nam | Phố cổ, đền chùa, hồ, bảo tàng |
| 2 | TP. Hồ Chí Minh | Hồ Chí Minh, Việt Nam | Di tích, nhà thờ, chợ, bảo tàng |
| 3 | Đà Nẵng | Đà Nẵng, Việt Nam | Biển, núi, cầu, Bà Nà Hills |
| 4 | Quảng Nam | Quảng Nam, Việt Nam | Hội An, Mỹ Sơn, Cù Lao Chàm |
| 5 | Thừa Thiên Huế | Huế, Việt Nam | Cố đô, lăng tẩm, chùa |
| 6 | Khánh Hòa | Nha Trang, Việt Nam | Biển, đảo, Vinpearl, tháp Chàm |
| 7 | Quảng Ninh | Quảng Ninh, Việt Nam | Vịnh Hạ Long, Yên Tử |
| 8 | Lâm Đồng | Đà Lạt, Việt Nam | Thác, hồ, vườn hoa, đồi chè |

---

## Tier 2 - Khá nhiều địa điểm

| STT | Tỉnh/Thành phố | City fallback | Đặc điểm nổi bật |
|-----|----------------|---------------|------------------|
| 9 | Lào Cai | Lào Cai, Việt Nam | Sa Pa, Fansipan, ruộng bậc thang |
| 10 | Ninh Bình | Ninh Bình, Việt Nam | Tràng An, Tam Cốc, chùa Bái Đính |
| 11 | Bình Thuận | Phan Thiết, Việt Nam | Mũi Né, đồi cát, hải đăng |
| 12 | Kiên Giang | Phú Quốc, Việt Nam | Đảo Phú Quốc, biển, Vinpearl |
| 13 | Bà Rịa-Vũng Tàu | Vũng Tàu, Việt Nam | Biển, tượng Chúa, hải đăng |
| 14 | Quảng Bình | Đồng Hới, Việt Nam | Phong Nha-Kẻ Bàng, Sơn Đoòng |
| 15 | Hải Phòng | Hải Phòng, Việt Nam | Cát Bà, Đồ Sơn |
| 16 | Cần Thơ | Cần Thơ, Việt Nam | Chợ nổi Cái Răng, vườn trái cây |

---

## Tier 3 - Trung bình

| STT | Tỉnh/Thành phố | City fallback | Đặc điểm nổi bật |
|-----|----------------|---------------|------------------|
| 17 | Bình Định | Quy Nhơn, Việt Nam | Biển, tháp Chàm, Ghềnh Ráng |
| 18 | Phú Yên | Tuy Hòa, Việt Nam | Gành Đá Đĩa, Mũi Điện |
| 19 | Hà Giang | Hà Giang, Việt Nam | Đèo Mã Pì Lèng, cao nguyên đá |
| 20 | An Giang | Châu Đốc, Việt Nam | Núi Sam, miếu Bà Chúa Xứ |
| 21 | Đắk Lắk | Buôn Ma Thuột, Việt Nam | Thác Dray Nur, hồ Lắk, buôn làng |
| 22 | Gia Lai | Pleiku, Việt Nam | Biển Hồ, thác Phú Cường |
| 23 | Thanh Hóa | Thanh Hóa, Việt Nam | Sầm Sơn, thành nhà Hồ |
| 24 | Nghệ An | Vinh, Việt Nam | Cửa Lò, quê Bác Hồ |

---

## Tier 4 - Ít hơn nhưng có điểm nổi bật

| STT | Tỉnh/Thành phố | City fallback | Đặc điểm nổi bật |
|-----|----------------|---------------|------------------|
| 25 | Cao Bằng | Cao Bằng, Việt Nam | Thác Bản Giốc, hang Pác Bó |
| 26 | Tây Ninh | Tây Ninh, Việt Nam | Núi Bà Đen, Tòa Thánh Cao Đài |
| 27 | Kon Tum | Kon Tum, Việt Nam | Nhà rông, nhà thờ gỗ |
| 28 | Sơn La | Sơn La, Việt Nam | Mộc Châu, thủy điện Sơn La |
| 29 | Điện Biên | Điện Biên, Việt Nam | Di tích Điện Biên Phủ |
| 30 | Bắc Ninh | Bắc Ninh, Việt Nam | Chùa Dâu, đình làng, quan họ |
| 31 | Ninh Thuận | Phan Rang, Việt Nam | Tháp Chàm Po Klong Garai, vườn nho |
| 32 | Bến Tre | Bến Tre, Việt Nam | Cồn Phụng, vườn dừa |

---

## Đề xuất thứ tự scrape

```
1. ✅ Đà Nẵng + Quảng Nam (đã có data)
2. ⏳ Khánh Hòa (Nha Trang)
3. ⏳ Lâm Đồng (Đà Lạt)
4. ⏳ Thừa Thiên Huế
5. ⏳ Quảng Ninh (Hạ Long)
6. ⏳ Hà Nội
7. ⏳ TP. Hồ Chí Minh
8. ⏳ Ninh Bình
9. ⏳ Lào Cai (Sa Pa)
10. ⏳ Kiên Giang (Phú Quốc)
```

---

## Code snippet

```python
# Danh sách tỉnh thành để scrape
PROVINCES_TO_SCRAPE = [
    # Tier 1
    {"name": "Hà Nội", "city": "Hà Nội, Việt Nam", "osm_name": "Thành phố Hà Nội"},
    {"name": "Hồ Chí Minh", "city": "Hồ Chí Minh, Việt Nam", "osm_name": "Thành phố Hồ Chí Minh"},
    {"name": "Đà Nẵng", "city": "Đà Nẵng, Việt Nam", "osm_name": "Thành phố Đà Nẵng"},
    {"name": "Quảng Nam", "city": "Quảng Nam, Việt Nam", "osm_name": "Tỉnh Quảng Nam"},
    {"name": "Thừa Thiên Huế", "city": "Huế, Việt Nam", "osm_name": "Tỉnh Thừa Thiên-Huế"},
    {"name": "Khánh Hòa", "city": "Nha Trang, Việt Nam", "osm_name": "Tỉnh Khánh Hòa"},
    {"name": "Quảng Ninh", "city": "Quảng Ninh, Việt Nam", "osm_name": "Tỉnh Quảng Ninh"},
    {"name": "Lâm Đồng", "city": "Đà Lạt, Việt Nam", "osm_name": "Tỉnh Lâm Đồng"},
    
    # Tier 2
    {"name": "Lào Cai", "city": "Lào Cai, Việt Nam", "osm_name": "Tỉnh Lào Cai"},
    {"name": "Ninh Bình", "city": "Ninh Bình, Việt Nam", "osm_name": "Tỉnh Ninh Bình"},
    {"name": "Bình Thuận", "city": "Phan Thiết, Việt Nam", "osm_name": "Tỉnh Bình Thuận"},
    {"name": "Kiên Giang", "city": "Phú Quốc, Việt Nam", "osm_name": "Tỉnh Kiên Giang"},
    {"name": "Bà Rịa-Vũng Tàu", "city": "Vũng Tàu, Việt Nam", "osm_name": "Tỉnh Bà Rịa-Vũng Tàu"},
    {"name": "Quảng Bình", "city": "Đồng Hới, Việt Nam", "osm_name": "Tỉnh Quảng Bình"},
    {"name": "Hải Phòng", "city": "Hải Phòng, Việt Nam", "osm_name": "Thành phố Hải Phòng"},
    {"name": "Cần Thơ", "city": "Cần Thơ, Việt Nam", "osm_name": "Thành phố Cần Thơ"},
    
    # Tier 3
    {"name": "Bình Định", "city": "Quy Nhơn, Việt Nam", "osm_name": "Tỉnh Bình Định"},
    {"name": "Phú Yên", "city": "Tuy Hòa, Việt Nam", "osm_name": "Tỉnh Phú Yên"},
    {"name": "Hà Giang", "city": "Hà Giang, Việt Nam", "osm_name": "Tỉnh Hà Giang"},
    {"name": "An Giang", "city": "Châu Đốc, Việt Nam", "osm_name": "Tỉnh An Giang"},
    {"name": "Đắk Lắk", "city": "Buôn Ma Thuột, Việt Nam", "osm_name": "Tỉnh Đắk Lắk"},
    {"name": "Gia Lai", "city": "Pleiku, Việt Nam", "osm_name": "Tỉnh Gia Lai"},
    {"name": "Thanh Hóa", "city": "Thanh Hóa, Việt Nam", "osm_name": "Tỉnh Thanh Hóa"},
    {"name": "Nghệ An", "city": "Vinh, Việt Nam", "osm_name": "Tỉnh Nghệ An"},
]
```

---

## Overpass Query Template

```
[out:json][timeout:180];
area["name"="<OSM_NAME>"]->.province;
(
  // Tourism
  nwr["tourism"="attraction"](area.province);
  nwr["tourism"="viewpoint"](area.province);
  nwr["tourism"="museum"](area.province);
  nwr["tourism"="gallery"](area.province);
  
  // Natural
  nwr["natural"="beach"](area.province);
  nwr["natural"="peak"](area.province);
  nwr["natural"="cave_entrance"](area.province);
  nwr["waterway"="waterfall"](area.province);
  
  // Historic
  nwr["historic"](area.province);
  
  // Religious
  nwr["amenity"="place_of_worship"](area.province);
  
  // Leisure
  nwr["leisure"="park"]["name"](area.province);
  nwr["leisure"="nature_reserve"](area.province);
  
  // Boundary
  nwr["boundary"="national_park"](area.province);
  nwr["boundary"="protected_area"](area.province);
);
out center;
```

Thay `<OSM_NAME>` bằng giá trị `osm_name` tương ứng.

---

## Ghi chú

- **Tier 1**: Scrape trước, dữ liệu phong phú nhất
- **Tier 2**: Scrape sau Tier 1, vẫn có nhiều địa điểm chất lượng
- **Tier 3-4**: Scrape khi cần mở rộng coverage

- **City fallback**: Dùng cho Google Maps scraper khi address không có
- **OSM name**: Dùng cho Overpass API query