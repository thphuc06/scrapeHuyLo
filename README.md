## 1\. Yêu Cầu và Cài Đặt

### 1.1. Yêu cầu Hệ thống

  * **Python 3.7+**
  * **Google Chrome** (để chạy Selenium)

### 1.2. Cài đặt Thư viện

Chạy lệnh sau để cài đặt các thư viện Python cần thiết:

```bash
pip install requests beautifulsoup4 selenium unidecode fuzzywuzzy
```

### 1.3. Cập nhật User-Agent

**Quan trọng:** Trước khi chạy, bạn cần cập nhật **email liên hệ** của mình trong file `overpass.py` để tuân thủ quy tắc sử dụng Nominatim và Overpass API.

Trong `overpass.py`, thay thế email của tôi bằng email của bạn:

```python
# overpass.py
# HÃY DÙNG EMAIL THẬT CỦA BẠN!
USER_AGENT_CONTACT = "OSMDataScraperVietNam/1.0 (your-email@example.com)" 
```

-----

## 2\. Quy Trình Thu Thập Dữ Liệu (2 Bước)

Quy trình được thực hiện theo 2 bước chính:

1.  **Bước 1 (OSM):** Dùng `overpass.py` để lấy danh sách POI cơ bản (ID, Tên, Tọa độ, Địa chỉ sơ bộ) cho một khu vực (thành phố/tỉnh).
2.  **Bước 2 (Google Maps):** Dùng `scrape_v6.py` để lấy thông tin chi tiết (rating, website, reviews...) cho từng POI từ file CSV đầu ra của Bước 1.

### 2.1. Bước 1: Thu Thập POI Thô từ OpenStreetMap (OSM)

Script `overpass.py` sẽ sử dụng **Nominatim** để lấy BBox và **Overpass QL** để lấy các POI du lịch cốt lõi (attraction, museum, park, historic, worship, natural...).

#### 🚀 Cách Chạy

Chạy file:

```bash
python overpass.py
```

Chương trình sẽ hiển thị danh sách các thành phố/tỉnh có sẵn để lựa chọn:

```
============================================================
🗺️  OSM OVERPASS SCAN (TINH LỌC DU LỊCH)
============================================================
1. Thành phố Đà Nẵng
...
11. Thành phố Hải Phòng

>>> Chọn số hoặc nhập tên thành phố: 
```

  * **Nhập số (ví dụ: `1`)** hoặc **nhập tên (ví dụ: `Thành phố Huế`)** để bắt đầu quét.
  * **Đầu ra:** Một file CSV (ví dụ: `Da_Nang_osm_core_data.csv`) chứa danh sách POI thô.

**💡 Chiến lược:** Đảm bảo file CSV đầu ra chứa các cột `id`, `name`, `address`, `lat`, `lon` để sử dụng cho Bước 2.

-----

### 2.2. Bước 2: Scrape Dữ liệu Chi Tiết từ Google Maps

Script `scrape_v6.py` sẽ đọc file CSV từ Bước 1 và sử dụng Selenium để scrape thông tin chi tiết.

#### 📁 Chuẩn bị File Input

Đổi tên file CSV từ Bước 1 thành tên dễ quản lý, ví dụ: `Da_Nang_seed.csv`.

#### 🚀 Cách Chạy (Cơ bản)

Chạy file:

```bash
# Chạy ở chế độ Headless (ẩn trình duyệt), scrape toàn bộ file CSV
python scrape_v6.py

# Chạy ở chế độ có giao diện (hiện trình duyệt)
python scrape_v6.py --no-headless
```

#### 🛠️ Lệnh Chạy Với Chỉ Số (Để Chạy Đa Luồng)

Bạn có thể chỉ định phạm vi các dòng (POI) cần scrape:

| Lệnh | Mô tả |
| :--- | :--- |
| `python scrape_v6.py <end_index>` | Scrape từ POI đầu tiên (index 0) đến `<end_index> - 1`. |
| `python scrape_v6.py <start_index> <end_index>` | Scrape từ `<start_index>` đến `<end_index> - 1`. |
| `python scrape_v6.py --expand` | Scrape toàn bộ file và kích hoạt chế độ **BFS Expansion** (tìm thêm các địa điểm liên quan). |

**Ví dụ:**

```bash
# Scrape 50 POI đầu tiên (từ 0 đến 49)
python scrape_v6.py 50

# Scrape 50 POI tiếp theo (từ 50 đến 99)
python scrape_v6.py 50 100
```

#### 📁 Thay Đổi File Input và City Fallback

Trong hàm `main()` của file `scrape_v6.py`, bạn cần thay đổi đường dẫn file CSV và tên thành phố/tỉnh fallback cho mỗi lần chạy:

```python
# scrape_v6.py (trong hàm main)
# ----------------------------------------------------------------------
csv_file = r"C:\HCMUS\ComputationalThinking\track-asia\test_museum.csv" # <-- THAY ĐỔI ĐƯỜNG DẪN NÀY
city = "Hồ Chí Minh, Việt Nam" # <-- THAY ĐỔI CITY FALLBACK NÀY

# ...

# Trong lệnh chạy:
scrape_csv_file(csv_file, headless=True,
                start_index=int(args[0]),
                end_index=int(args[1]),
                city=city, # <-- City fallback được truyền vào đây
                expand_related=expand_mode)
```

**Đầu ra:** Một hoặc nhiều file JSON (ví dụ: `Da_Nang_seed_scraped_0_50.json`) chứa dữ liệu chi tiết.

-----

## 3\. Chiến Lược Scrape Theo Tỉnh Thành (Dựa trên `PLACE.md`)

File `PLACE.md` cung cấp danh sách và thứ tự ưu tiên các tỉnh thành. Để cào từng khu vực cụ thể:

### 3.1. Thao tác với Overpass (`overpass.py`)

File `overpass.py` hiện đã tích hợp một số thành phố. Để cào theo **tỉnh/thành phố lớn** (ví dụ: Tỉnh Quảng Nam), bạn cần cập nhật dictionary `CITIES` và hàm `build_overpass_query` để sử dụng Nominatim hoặc Overpass Area ID cho tỉnh đó.

**Cách làm dễ nhất là cào các thành phố đã có sẵn trong `overpass.py` trước.**

```python
# overpass.py (ví dụ về CITIES)
CITIES = {
    # ...
    "Thành phố Hội An": "Hoi_An", # Thành phố trực thuộc tỉnh Quảng Nam
    "Thành phố Huế": "Hue", # Thành phố trực thuộc tỉnh Thừa Thiên Huế
    # ...
}
```

### 3.2. Cấu hình cho Google Maps Scraper (`scrape_v6.py`)

Dựa vào file `PLACE.md`, bạn có thể xác định `city` fallback chính xác cho từng lần chạy `scrape_v6.py`.

Sử dụng phần `Code snippet` trong `PLACE.md`:

```python
# PROVINCES_TO_SCRAPE trong PLACE.md
[
    {"name": "Hà Nội", "city": "Hà Nội, Việt Nam", "osm_name": "Thành phố Hà Nội"},
    {"name": "Quảng Nam", "city": "Quảng Nam, Việt Nam", "osm_name": "Tỉnh Quảng Nam"},
    # ...
]
```

**Các bước cho mỗi tỉnh/thành phố:**

1.  **Chỉnh `overpass.py`:** Chạy `overpass.py` và chọn (hoặc thêm) thành phố/tỉnh bạn muốn cào.

      * **Ví dụ:** Chạy cho `Thành phố Đà Lạt`, tạo ra `Da_Lat_osm_core_data.csv`.

2.  **Đổi tên Input:** Đổi tên file CSV thành `Da_Lat_seed.csv`.

3.  **Cấu hình `scrape_v6.py`:** Cập nhật `csv_file` và `city` fallback trong `scrape_v6.py/main()`:

    ```python
    # scrape_v6.py (main function)
    csv_file = r"path/to/Da_Lat_seed.csv"
    city = "Đà Lạt, Việt Nam" # (Từ cột City fallback của Lâm Đồng trong PLACE.md)
    ```

4.  **Chạy Scrape:** Chạy `scrape_v6.py` với cấu hình này.

-----

## 4\. Hướng Dẫn Chạy Đa Luồng (Multi-Terminal)

Để tối ưu hóa thời gian scrape, bạn nên chạy nhiều phiên bản của `scrape_v6.py` song song bằng cách chia file CSV thành các phần nhỏ (batch) và chạy mỗi phần trên một terminal (hoặc session).

**Ví dụ:** File `Da_Nang_seed.csv` có 300 POI.

1.  **Chia batch:**

      * Batch 1: Index 0 - 99 (100 POI)
      * Batch 2: Index 100 - 199 (100 POI)
      * Batch 3: Index 200 - 299 (100 POI)

2.  **Mở 3 Terminal (hoặc 3 cửa sổ/tab):**

    | Terminal | Lệnh Chạy | Output File |
    | :--- | :--- | :--- |
    | **Terminal 1** | `python scrape_v6.py 0 100` | `Da_Nang_seed_scraped_0_100.json` |
    | **Terminal 2** | `python scrape_v6.py 100 200` | `Da_Nang_seed_scraped_100_200.json` |
    | **Terminal 3** | `python scrape_v6.py 200 300` | `Da_Nang_seed_scraped_200_300.json` |

3.  **Gộp file (Sau khi hoàn tất):**

    Chạy lệnh merge trong thư mục chứa các file JSON kết quả:

    ```bash
    python scrape_v6.py merge .
    ```

    (Dấu chấm `.` chỉ định thư mục hiện tại. Nếu cần, thay đổi thành đường dẫn thư mục chứa file JSON).
