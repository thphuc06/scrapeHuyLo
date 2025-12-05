# -*- coding: utf-8 -*-
"""
Google Maps Scraper V5.7 - SMART SEARCH + BFS EXPANSION
- Fix address extraction (loại bỏ rating, category lẫn vào)
- Tối ưu lấy phone, website
- Lấy opening_hours chi tiết từ T2-CN
- Smart search strategy (name+address / name+city / name+coords)
- IMPROVED: Expansion mode - Lấy related places từ "Mọi người cũng tìm kiếm" bằng cách extract names từ aria-label trên div.Lnaw4c
  + Tăng scroll times/sleep để load section
  + Specific selector cho div[class*='Lnaw4c'] với aria-label matching pattern
  + Không cần URL/lat/lon, chỉ lấy name và search by name only
  + Thêm debug nâng cao: check heading by text, limit search trong section, print sample aria-labels, total aria elements
- Loại bỏ field related_places trong output (chỉ scrape chúng như các place riêng biệt qua BFS)
- Clean output
- Chỉnh sửa search: Đối với related places từ GMaps, search chỉ bằng name
- Giữ nguyên các phần khác
"""
import os
import sys
import csv
import json
import time
import random
import urllib.parse
import re
from typing import Optional, List, Tuple
from datetime import datetime
from collections import deque
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from unidecode import unidecode

# Fix encoding on Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


# ============================================================
# CONFIGURATION - Thay đổi theo nhu cầu
# ============================================================
DEFAULT_CITY = "Đà Nẵng, Việt Nam"  # City mặc định khi không có address
BFS_MAX_PLACES = 1000  # Giới hạn tối đa places trong BFS để tránh vô hạn
BFS_MAX_DEPTH = 3  # Độ sâu tối đa trong BFS (từ seed places)


def normalize_place_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    name = unidecode(name)
    name = re.sub(r'\s*-\s*chi nhanh.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*-\s*branch.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s]', ' ', name)
    name = ' '.join(name.split())
    return name


def extract_name_from_google_maps_url(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        match = re.search(r'/place/([^/@]+)', url)
        if match:
            encoded_name = match.group(1)
            decoded_name = urllib.parse.unquote(encoded_name)
            decoded_name = decoded_name.replace('+', ' ')
            return decoded_name
    except:
        pass
    return None


def clean_address(addr: str) -> Optional[str]:
    """Clean địa chỉ - loại bỏ rating, category, directions bị lẫn vào"""
    if not addr or len(addr) < 5:
        return None
    
    # Pattern KHÔNG hợp lệ
    invalid_patterns = [
        r'\d+[,.]?\d*\s*\(\d',      # 4,1(903 - rating
        r'·',                        # Google separator
        r'Điểm thu hút',
        r'Điểm mốc',
        r'Đường đi',
        r'Mở cửa',
        r'Đóng cửa',
        r'Sắp đóng',
        r'Sắp mở',
        r'\bsao\b',
        r'\bstar\b',
        r'Khách sạn nghỉ',
        r'Bể bơi',
        r'Wi-Fi',
        r'Được tài trợ',
        r'Của Agoda',
        r'Booking\.com',
        r'Đại lý du lịch',
        r'Công viên xe',
        r'Phòng cho thuê',
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, addr, re.IGNORECASE):
            return None
    
    addr = re.sub(r'\s+', ' ', addr).strip()
    
    # Validate
    valid_keywords = [
        'đường', 'phố', 'quận', 'huyện', 'tỉnh', 'thành phố', 'tp',
        'phường', 'xã', 'thị trấn', 'ấp', 'thôn', 'số', 'ngõ', 'ngách',
        'street', 'road', 'district', 'city', 'province', 'ward',
        'việt nam', 'vietnam', 'vn', 'khánh hòa', 'nha trang',
    ]
    
    addr_lower = addr.lower()
    has_valid = any(kw in addr_lower for kw in valid_keywords)
    has_number = bool(re.search(r'\d', addr))
    
    if has_valid or (has_number and len(addr) > 15):
        return addr
    
    return None


def clean_website_url(url: str) -> Optional[str]:
    if not url:
        return None
    
    if "google.com/url" in url and "?q=" in url:
        try:
            match = re.search(r'[?&]q=([^&]+)', url)
            if match:
                return urllib.parse.unquote(match.group(1))
        except:
            pass
    
    if "google.com/maps" in url:
        return None
    
    return url


def is_valid_address(address: str) -> bool:
    """Kiểm tra address có đủ tốt để search không"""
    if not address:
        return False
    address = address.strip()
    if len(address) < 10:
        return False
    # Kiểm tra có chứa thông tin địa lý không
    geo_keywords = ['đường', 'phố', 'quận', 'huyện', 'phường', 'xã',
                    'thành phố', 'việt nam', 'vietnam', ',']
    return any(kw in address.lower() for kw in geo_keywords)


def validate_address_match(original_address: str, scraped_address: str) -> bool:
    """
    Kiểm tra địa chỉ scrape có khớp với địa chỉ gốc không

    Returns:
        True nếu 2 địa chỉ khớp nhau (hoặc không có địa chỉ gốc)
        False nếu 2 địa chỉ hoàn toàn không liên quan
    """
    # Nếu không có địa chỉ gốc, chấp nhận địa chỉ scrape
    if not original_address or len(original_address.strip()) < 5:
        return True

    # Nếu không scrape được địa chỉ, return True (giữ null)
    if not scraped_address:
        return True

    # Normalize cả 2 địa chỉ
    orig_norm = unidecode(original_address.lower()).strip()
    scrap_norm = unidecode(scraped_address.lower()).strip()

    # Nếu 2 địa chỉ quá giống nhau (>= 70% similarity)
    if fuzz.partial_ratio(orig_norm, scrap_norm) >= 70:
        return True

    # Kiểm tra có chung các từ khóa địa lý quan trọng không
    # (quận, phường, đường, thành phố...)
    orig_words = set(orig_norm.split())
    scrap_words = set(scrap_norm.split())

    # Các từ khóa quan trọng phải match
    important_keywords = ['quan', 'phuong', 'duong', 'pho', 'xa', 'huyen',
                         'thanh pho', 'tinh', 'district', 'ward', 'street']

    orig_important = {w for w in orig_words if any(k in w for k in important_keywords)}
    scrap_important = {w for w in scrap_words if any(k in w for k in important_keywords)}

    # Nếu có ít nhất 1 từ khóa quan trọng chung -> OK
    if orig_important & scrap_important:
        return True

    # Nếu địa chỉ gốc có thông tin địa lý nhưng scrape hoàn toàn khác -> REJECT
    if orig_important and scrap_important and not (orig_important & scrap_important):
        return False

    # Fallback: nếu có ít nhất 2 từ chung (không tính từ phổ biến)
    common_words = ['viet', 'nam', 'vietnam', 'vn', 'so', 'number']
    meaningful_common = (orig_words & scrap_words) - set(common_words)

    if len(meaningful_common) >= 2:
        return True

    # Ngược lại: 2 địa chỉ không khớp
    return False


class GoogleMapsScraper:
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def __init__(self, headless: bool = True, default_city: str = DEFAULT_CITY):
        self.headless = headless
        self.driver = None
        self.default_city = default_city
        self.current_lat = None  # Track current place coords
        self.current_lon = None

    def init_driver(self):
        if self.driver:
            return

        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(f'--user-agent={random.choice(self.USER_AGENTS)}')
        chrome_options.add_argument('--lang=vi')
        chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'vi,en'})

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        print("[OK] WebDriver initialized")

    def _get_address(self) -> Optional[str]:
        """Lấy địa chỉ - CHỈ từ nguồn đáng tin"""
        
        # Strategy 1: data-item-id='address'
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, "button[data-item-id='address']")
            aria = btn.get_attribute("aria-label")
            if aria:
                addr = aria.replace("Địa chỉ: ", "").replace("Address: ", "").strip()
                cleaned = clean_address(addr)
                if cleaned:
                    return cleaned
        except:
            pass
        
        # Strategy 2: aria-label bắt đầu "Địa chỉ:"
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label]")
            for btn in buttons:
                aria = btn.get_attribute("aria-label") or ""
                if aria.startswith("Địa chỉ:") or aria.startswith("Address:"):
                    addr = aria.split(":", 1)[-1].strip()
                    cleaned = clean_address(addr)
                    if cleaned:
                        return cleaned
        except:
            pass
        
        # Strategy 3: Tìm div.Io6YTe trong button address
        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            for btn in soup.find_all('button', attrs={'data-item-id': True}):
                if 'address' in btn.get('data-item-id', '').lower():
                    text_div = btn.find('div', class_=lambda x: x and 'Io6YTe' in str(x))
                    if text_div:
                        addr = text_div.get_text(strip=True)
                        cleaned = clean_address(addr)
                        if cleaned:
                            return cleaned
        except:
            pass
        
        return None

    def _get_phone(self) -> Optional[str]:
        try:
            btns = self.driver.find_elements(By.CSS_SELECTOR, "button[data-item-id^='phone:tel:']")
            for btn in btns:
                data_id = btn.get_attribute("data-item-id")
                if data_id and "phone:tel:" in data_id:
                    phone = data_id.replace("phone:tel:", "").strip()
                    if phone and len(phone) >= 8:
                        return phone
        except:
            pass
        
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label]")
            for btn in buttons:
                aria = btn.get_attribute("aria-label") or ""
                if "Điện thoại:" in aria or "Phone:" in aria:
                    match = re.search(r'[\d\s\-\+\(\)]{8,}', aria)
                    if match:
                        return match.group(0).strip()
        except:
            pass
        
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href^='tel:']")
            for link in links:
                href = link.get_attribute("href")
                if href:
                    phone = href.replace("tel:", "").strip()
                    if len(phone) >= 8:
                        return phone
        except:
            pass
        
        return None

    def _get_website(self) -> Optional[str]:
        raw_url = None
        
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[data-item-id='authority']")
            if links:
                raw_url = links[0].get_attribute("href")
        except:
            pass
        
        if not raw_url:
            try:
                links = self.driver.find_elements(By.CSS_SELECTOR, "a[aria-label*='website'], a[aria-label*=' Trang web']")
                for link in links:
                    href = link.get_attribute("href")
                    if href and not href.startswith("tel:"):
                        raw_url = href
                        break
            except:
                pass
        
        return clean_website_url(raw_url)

    def _get_price_level(self) -> Optional[str]:
        try:
            spans = self.driver.find_elements(By.CSS_SELECTOR, "span[aria-label*='Price'], span[aria-label*='Giá']")
            for span in spans:
                aria = span.get_attribute("aria-label") or ""
                if "đánh giá" in aria.lower():
                    continue
                if "Price:" in aria:
                    return aria.split("Price:")[-1].strip()
                if "Giá:" in aria:
                    return aria.split("Giá:")[-1].strip()
        except:
            pass
        
        try:
            spans = self.driver.find_elements(By.TAG_NAME, "span")
            for span in spans:
                text = span.text.strip()
                if re.match(r'^[\$₫]{1,4}$', text):
                    return text
        except:
            pass
        
        return None

    def _get_about(self) -> Optional[List[str]]:
        """
        Lấy About section - trả về list tất cả features
        Format: ["Có: Picnic tables", "Không: Wheelchair accessible entrance", ...]
        """
        features = []
        seen = set()
        
        try:
            # Click tab About/Giới thiệu
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "button[role='tab']")
            clicked = False
            for tab in tabs:
                tab_text = tab.text.lower()
                if any(x in tab_text for x in ["about", "giới thiệu", "thông tin"]):
                    tab.click()
                    time.sleep(2.5)
                    clicked = True
                    break
            
            if not clicked:
                return None
            
            # Scroll nhiều lần để load hết content
            try:
                scrollables = self.driver.find_elements(By.CSS_SELECTOR, "div[role='main'], div.m6QErb")
                for scrollable in scrollables:
                    for _ in range(5):
                        self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable)
                        time.sleep(0.3)
            except:
                pass
            
            # Helper function để parse và add feature
            def add_feature(aria: str):
                if not aria or len(aria) < 3:
                    return
                
                if len(aria) > 100: return 

                feature = None
                
                if aria.startswith("Có: "):
                    feature = "Có: " + aria[4:].strip()
                elif aria.startswith("Không: "):
                    feature = "Không: " + aria[7:].strip()
                elif aria.startswith("Có "):
                    feature = "Có: " + aria[3:].strip()
                elif aria.startswith("Không "):
                    feature = "Không: " + aria[6:].strip()
                elif aria.startswith("Chấp nhận "):
                    feature = "Có: " + aria[10:].strip()
                elif aria.startswith("Phù hợp "):
                    feature = "Có: " + aria 
                elif aria.startswith("Thích hợp "):
                    feature = "Có: " + aria
                elif aria.startswith("Yes: "):
                    feature = "Có: " + aria[5:].strip()
                elif aria.startswith("No: "):
                    feature = "Không: " + aria[4:].strip()
                elif aria.startswith("Has "):
                    feature = "Có: " + aria[4:].strip()
                elif aria.startswith("Doesn't have "):
                    feature = "Không: " + aria[13:].strip()
                elif aria.startswith("No "):
                    feature = "Không: " + aria[3:].strip()
                elif aria.startswith("Accepts "):
                    feature = "Có: " + aria[8:].strip()
                elif aria.startswith("Good for "):
                    feature = "Có: " + aria
                elif aria.startswith("Picnic"): 
                    feature = "Có: " + aria
                elif aria.startswith("Wifi"):
                    feature = "Có: " + aria
                elif aria.startswith("Toilet"):
                    feature = "Có: " + aria
                elif aria.startswith("Restroom"):
                    feature = "Có: " + aria
                elif aria.startswith("Parking"):
                    feature = "Có: " + aria
                elif aria.startswith("Wheelchair"):
                    feature = "Có: " + aria

                if feature and feature not in seen and len(feature) > 5:
                    seen.add(feature)
                    features.append(feature)
            
            # Strategy 1: Selenium
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, "[aria-label]")
                for elem in elements:
                    try:
                        aria = elem.get_attribute("aria-label")
                        add_feature(aria)
                    except:
                        continue
            except:
                pass
            
            # Strategy 2: BeautifulSoup
            try:
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                for elem in soup.find_all(attrs={'aria-label': True}):
                    aria = elem.get('aria-label', '')
                    add_feature(aria)
                
                for li in soup.find_all('li'):
                    aria = li.get('aria-label', '')
                    if aria:
                        add_feature(aria)
                    for child in li.find_all(['span', 'div']):
                        aria = child.get('aria-label', '')
                        if aria:
                            add_feature(aria)
                
                for item in soup.find_all(attrs={'role': 'listitem'}):
                    aria = item.get('aria-label', '')
                    if aria:
                        add_feature(aria)
                    for child in item.find_all(attrs={'aria-label': True}):
                        add_feature(child.get('aria-label', ''))
                
                for img in soup.find_all('img', attrs={'aria-label': True}):
                    aria = img.get('aria-label', '')
                    add_feature(aria)
                    
            except:
                pass
            
            # Strategy 3: Tìm theo pattern class
            try:
                feature_divs = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='iNvpkc'], li[class*='hpLkke']")
                for div in feature_divs:
                    try:
                        aria = div.get_attribute("aria-label")
                        if aria:
                            add_feature(aria)
                        children = div.find_elements(By.CSS_SELECTOR, "[aria-label]")
                        for child in children:
                            add_feature(child.get_attribute("aria-label"))
                    except:
                        continue
            except:
                pass
            
        except Exception as e:
            print(f"   [WARNING] About error: {e}")
        
        return features if features else None

    def _get_comments(self, num: int = 3) -> List[dict]:
        """
        Lấy comments với full text (click "Thêm" để expand)
        """
        comments = []
        try:
            # Click tab Reviews/Đánh giá
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "button[role='tab']")
            for tab in tabs:
                if any(x in tab.text.lower() for x in ["đánh giá", "review"]):
                    tab.click()
                    time.sleep(1.5)
                    break
            
            # Scroll để load reviews
            try:
                scrollable = self.driver.find_element(By.CSS_SELECTOR, "div[role='main']")
                for _ in range(3):
                    self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable)
                    time.sleep(0.5)
            except:
                pass
            
            # === CLICK TẤT CẢ NÚT "THÊM" ĐỂ EXPAND COMMENT ===
            try:
                # Tìm tất cả button "Thêm" / "More" trong reviews
                more_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    "button.w8nwRe.kyuRq, button[aria-label='Xem thêm'], button[jsaction*='review.expandReview']")
                
                for btn in more_buttons:
                    try:
                        # Chỉ click nếu button visible và có text "Thêm" hoặc "More"
                        if btn.is_displayed():
                            btn_text = btn.text.strip().lower()
                            if btn_text in ['thêm', 'more', 'see more', 'xem thêm']:
                                btn.click()
                                time.sleep(0.3)
                    except:
                        continue
                
                # Fallback: Tìm theo class w8nwRe (Google Maps dùng class này cho "Thêm")
                more_buttons2 = self.driver.find_elements(By.CSS_SELECTOR, "button.w8nwRe")
                for btn in more_buttons2:
                    try:
                        if btn.is_displayed() and btn.text.strip().lower() in ['thêm', 'more']:
                            btn.click()
                            time.sleep(0.3)
                    except:
                        continue
                        
            except Exception as e:
                print(f"   [WARNING] Click 'Thêm' error: {e}")
            
            # Đợi content expand
            time.sleep(0.5)
            
            # Parse reviews sau khi đã expand
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            review_divs = soup.find_all('div', {'data-review-id': True})
            
            seen = set()
            for div in review_divs:
                rid = div.get('data-review-id')
                if rid and rid not in seen:
                    seen.add(rid)
                    try:
                        # Author
                        author_elem = div.find('div', class_=lambda x: x and 'd4r55' in str(x))
                        author = author_elem.text.strip() if author_elem else "Anonymous"
                        
                        # Rating
                        rating_elem = div.find('span', {'role': 'img', 'aria-label': True})
                        rating_text = rating_elem.get('aria-label', '') if rating_elem else ''
                        rating_match = re.search(r'(\d+)', rating_text)
                        rating = float(rating_match.group(1)) if rating_match else 0.0
                        
                        # Text - lấy từ span.wiI7pd (đã được expand)
                        text_elem = div.find('span', class_=lambda x: x and 'wiI7pd' in str(x))
                        text = text_elem.text.strip() if text_elem else ""
                        
                        # Date
                        time_elem = div.find('span', class_=lambda x: x and 'rsqaWe' in str(x))
                        date = None
                        if time_elem:
                            time_text = time_elem.text.strip()
                            date = self._convert_relative_date(time_text)
                        
                        if text and len(text) > 5:
                            comments.append({
                                "author": author,
                                "rating": rating,
                                "text": text,
                                "date": date
                            })
                        
                        if len(comments) >= num:
                            break
                    except:
                        continue
        except:
            pass
        
        return comments
    
    def _convert_relative_date(self, relative_time: str) -> Optional[str]:
        """Convert '3 tháng trước' -> '03/09/2024'"""
        if not relative_time:
            return None
        
        from datetime import timedelta
        now = datetime.now()
        text = relative_time.lower()
        
        try:
            num_match = re.search(r'(\d+)', text)
            num = int(num_match.group(1)) if num_match else 1
            
            if any(x in text for x in ['day', 'ngày', 'ngay']):
                date = now - timedelta(days=num)
            elif any(x in text for x in ['week', 'tuần', 'tuan']):
                date = now - timedelta(weeks=num)
            elif any(x in text for x in ['month', 'tháng', 'thang']):
                date = now - timedelta(days=num * 30)
            elif any(x in text for x in ['year', 'năm', 'nam']):
                date = now - timedelta(days=num * 365)
            else:
                return None
            
            return date.strftime("%d/%m/%Y")
        except:
            return None

    def _get_hours(self) -> Optional[dict]:
        """
        Lấy opening hours từ T2 - CN
        
        Returns:
            dict: {"Thứ Hai": "08:00-17:00", ...} hoặc None
        """
        result = {}
        
        try:
            # Step 1: Click button giờ mở cửa để mở dropdown
            try:
                hour_btn = self.driver.find_element(By.CSS_SELECTOR, "button[data-item-id='oh']")
                if hour_btn.get_attribute("aria-expanded") != "true":
                    hour_btn.click()
                    time.sleep(1.2)
            except:
                # Fallback: tìm button có chứa text giờ
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Đang mở'], button[aria-label*='Đã đóng']")
                    for btn in buttons:
                        btn.click()
                        time.sleep(1.2)
                        break
                except:
                    pass
            
            # Step 2: Parse table giờ mở cửa
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Tìm table chứa giờ (class eK4R0e)
            table = soup.find('table', class_=lambda x: x and 'eK4R0e' in str(x))
            
            if table:
                rows = table.find_all('tr', class_=lambda x: x and 'y0skZc' in str(x))
                
                for row in rows:
                    # Lấy tên ngày từ td.ylH6lf
                    day_td = row.find('td', class_=lambda x: x and 'ylH6lf' in str(x))
                    
                    # Lấy giờ từ td.mxowUb
                    time_td = row.find('td', class_=lambda x: x and 'mxowUb' in str(x))
                    
                    if day_td and time_td:
                        day_name = day_td.get_text(strip=True)
                        
                        # Ưu tiên lấy từ aria-label
                        hours_text = time_td.get('aria-label', '')
                        
                        # Fallback: lấy từ li.G8aQO
                        if not hours_text:
                            li = time_td.find('li', class_=lambda x: x and 'G8aQO' in str(x))
                            if li:
                                hours_text = li.get_text(strip=True)
                        
                        # Fallback: lấy text trực tiếp
                        if not hours_text:
                            hours_text = time_td.get_text(strip=True)
                        
                        if day_name and hours_text:
                            # Clean format: "08:00 đến 17:00" -> "08:00-17:00"
                            hours_text = hours_text.replace(' đến ', '-').replace('đến', '-')
                            hours_text = hours_text.replace('–', '-')  # en-dash -> hyphen
                            result[day_name] = hours_text
            
            # Step 3: Fallback - Selenium trực tiếp nếu BeautifulSoup fail
            if not result:
                try:
                    rows = self.driver.find_elements(By.CSS_SELECTOR, "table.eK4R0e tr.y0skZc")
                    for row in rows:
                        day_td = row.find_element(By.CSS_SELECTOR, "td.ylH6lf")
                        time_td = row.find_element(By.CSS_SELECTOR, "td.mxowUb")
                        
                        day_name = day_td.text.strip()
                        hours_text = time_td.get_attribute("aria-label") or time_td.text.strip()
                        hours_text = hours_text.replace(' đến ', '-').replace('đến', '-').replace('–', '-')
                        
                        if day_name and hours_text:
                            result[day_name] = hours_text
                except:
                    pass
                    
        except Exception as e:
            print(f"   [WARNING] Hours error: {e}")
        
        return result if result else None

    def _get_images(self) -> List[str]:
        images = []
        try:
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "button[role='tab']")
            for tab in tabs:
                if any(x in tab.text.lower() for x in ["photo", "hình", "ảnh"]):
                    tab.click()
                    time.sleep(1.5)
                    break
            
            for _ in range(2):
                self.driver.execute_script("window.scrollBy(0, 300)")
                time.sleep(0.3)
            
            imgs = self.driver.find_elements(By.TAG_NAME, "img")
            seen = set()
            
            for img in imgs:
                try:
                    src = img.get_attribute("src")
                    if src and ("googleusercontent.com" in src or "ggpht.com" in src) and "=w" in src:
                        if any(x in src for x in ["=w30", "=w48", "=w24", "=w32", "=w64", "=w36"]):
                            continue
                        
                        match = re.search(r'=w(\d+)', src)
                        if match and int(match.group(1)) >= 100:
                            base = src.split('=w')[0]
                            if base not in seen:
                                seen.add(base)
                                images.append(src)
                                if len(images) >= 3:
                                    break
                except:
                    continue
        except:
            pass
        
        return images

    def _get_rating(self) -> Tuple[Optional[float], Optional[int]]:
        rating = None
        count = None
        
        try:
            elem = self.driver.find_element(By.CSS_SELECTOR, "span[aria-label*='sao']")
            text = elem.get_attribute("aria-label")
            m = re.search(r'(\d+[,.]?\d*)\s*sao', text)
            if m:
                rating = float(m.group(1).replace(',', '.'))
            m = re.search(r'(\d+[\.,]?\d*)\s*đánh giá', text)
            if m:
                count = int(m.group(1).replace('.', '').replace(',', ''))
        except:
            pass
        
        if rating is None:
            try:
                elem = self.driver.find_element(By.CSS_SELECTOR, "span[aria-label*='star']")
                text = elem.get_attribute("aria-label")
                m = re.search(r'(\d+[,.]?\d*)\s*star', text)
                if m:
                    rating = float(m.group(1).replace(',', '.'))
                m = re.search(r'(\d+[\.,]?\d*)\s*review', text)
                if m:
                    count = int(m.group(1).replace('.', '').replace(',', ''))
            except:
                pass
        
        if rating is None:
            try:
                divs = self.driver.find_elements(By.CSS_SELECTOR, "div.fontDisplayLarge")
                for div in divs:
                    text = div.text.strip()
                    if re.match(r'^\d+[,.]?\d*$', text):
                        val = float(text.replace(',', '.'))
                        if 1.0 <= val <= 5.0:
                            rating = val
                            break
            except:
                pass
        
        if count is None:
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
                for btn in buttons:
                    m = re.search(r'\((\d{1,3}(?:[,\.]\d{3})*)\)', btn.text)
                    if m:
                        count = int(m.group(1).replace(',', '').replace('.', ''))
                        break
            except:
                pass
        
        return rating, count

    def _get_category(self) -> Optional[str]:
        """Lấy category/type từ Google Maps"""
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[jsaction*='category']")
            for btn in buttons:
                text = btn.text.strip()
                if text and 3 < len(text) < 50:
                    return text
        except:
            pass

        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, "button.DkEaL")
            return btn.text.strip()
        except:
            pass

        return None

    def _get_related_place_names(self) -> List[str]:
        """
        Lấy tên các địa điểm liên quan từ "Mọi người cũng tìm kiếm" / "People also search for"
        bằng cách tìm div[class*='Lnaw4c'] với aria-label matching pattern "Name rating sao-count đánh giá gợi ý"

        Returns:
            List[str]: Các tên địa điểm
        """
        related_names = []
        seen = set()

        try:
            # Scroll nhiều lần để load section (tăng lên 10 lần để chắc chắn hơn)
            try:
                scrollable = self.driver.find_element(By.CSS_SELECTOR, "div[role='main']")
                for _ in range(10):
                    self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable)
                    time.sleep(1.0)  # Tăng sleep time
            except:
                print("   [DEBUG] No scrollable div[role='main'] found.")
            
            # Đợi thêm để content load
            time.sleep(3)

            # Sử dụng BeautifulSoup để parse page source
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Debug nâng cao: Tìm heading bằng text pattern (không rely on tag)
            heading_pattern = re.compile(r'mọi người cũng tìm kiếm|people also search for', re.IGNORECASE)
            heading_elem = soup.find(string=heading_pattern)
            if heading_elem:
                print("   [DEBUG] Related section heading found: " + heading_elem.strip())
                # Tìm parent section (ancestor div)
                section = heading_elem.find_parent('div', attrs={'role': 'region'}) or heading_elem.find_parent('div')
                if section:
                    print("   [DEBUG] Related section parent found.")
                else:
                    section = soup  # Fallback toàn page
            else:
                print("   [DEBUG] No related section heading found.")

            # Debug: Tổng số elements có aria-label
            all_aria_elements = soup.find_all(attrs={'aria-label': True})
            print(f"   [DEBUG] Total elements with aria-label: {len(all_aria_elements)}")

            # Tìm divs với class containing 'Lnaw4c' trong section (hoặc toàn page nếu không có section)
            elements = section.find_all('div', class_=lambda x: x and 'lnaw4c' in str(x).lower())  # Lowercase to match
            print(f"   [DEBUG] Number of divs with 'lnaw4c' in class: {len(elements)}")

            # Pattern để match aria-label của related places
            # Flexible regex: support dấu chấm/phẩy trong rating/count, optional spaces/dash
            pattern = re.compile(r'.+ \d[.,]\d\s*sao\s*[-–\s]*[\d.,]+\s*đánh giá\s*gợi ý$', re.IGNORECASE)

            # Debug: Print top 10 aria-labels trong section để check
            aria_samples = [elem.get('aria-label', '').strip() for elem in all_aria_elements[:10]]
            print("   [DEBUG] Sample aria-labels (top 10):")
            for sample in aria_samples:
                if sample:
                    print(f"     - {sample[:100]}...")  # Giới hạn dài

            for elem in elements:
                aria = elem.get('aria-label', '').strip()
                print(f"   [DEBUG] Aria-label found in Lnaw4c div: {aria[:100]}...")
                if pattern.match(aria):
                    print(f"   [DEBUG] Matched aria-label: {aria}")
                    # Extract name using regex match
                    match = re.match(r'^(.*?) \d[.,]\d\s*sao\s*[-–\s]*[\d.,]+\s*đánh giá\s*gợi ý$', aria, re.IGNORECASE)
                    if match:
                        name = match.group(1).strip()
                        print(f"   [DEBUG] Extracted name: {name}")
                        name = re.sub(r'\s+', ' ', name).strip()
                        if name and len(name) > 5 and name not in seen:
                            seen.add(name)
                            related_names.append(name)

        except Exception as e:
            print(f"   [ERROR] Get related places: {e}")

        # Deduplicate
        unique_names = list(seen)

        return unique_names

    def _build_search_url(self, name: str, address: str, lat: float, lon: float, city: str = None, force_name_only: bool = False) -> Tuple[str, str]:
        """
        Tạo URL search thông minh
        
        Returns:
            Tuple[url, search_method]: URL và phương thức search đã dùng
        """
        city = city or self.default_city
        
        if force_name_only:
            # Chỉ search bằng name cho related places (tên từ GMaps chuẩn)
            search_query = name
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}"
            return url, f"name_only: {search_query[:50]}..."
        
        # Case 1: Có address tốt -> search name + address
        if is_valid_address(address):
            search_query = f"{name}, {address}"
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}"
            return url, f"name+addr: {search_query[:50]}..."
        
        # Case 2: Có city -> search name + city
        if city:
            search_query = f"{name}, {city}"
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}"
            return url, f"name+city: {search_query[:50]}..."
        
        # Case 3: Fallback -> search name @coords (chính xác nhất khi không có gì)
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(name)}/@{lat},{lon},17z"
        return url, f"name+coords: {name[:30]}... @{lat:.4f},{lon:.4f}"

    def scrape_place(self, name: str, address: str, lat: float, lon: float,
                     num_reviews: int = 3, city: str = None, get_related: bool = False,
                     force_name_only: bool = False) -> dict:
        """
        Scrape thông tin địa điểm từ Google Maps

        SMART SEARCH STRATEGY:
        1. name + address (nếu address tốt - có đường, phường, quận...)
        2. name + city (nếu không có address đủ tốt)
        3. name @lat,lon (fallback - chính xác nhất khi không có gì)
        - Nếu force_name_only=True (cho related), chỉ search bằng name

        Args:
            name: Tên địa điểm
            address: Địa chỉ (có thể rỗng)
            lat: Latitude
            lon: Longitude
            num_reviews: Số review cần lấy
            city: Thành phố (dùng khi address không tốt)
            get_related: Có lấy related places không (mặc định False)
            force_name_only: Chỉ search bằng name (cho related places từ GMaps)
        """
        if not self.driver:
            self.init_driver()

        # Track current place coordinates for related places extraction
        self.current_lat = lat
        self.current_lon = lon

        result = {
            "name": name,
            "original_address": address,
            "new_address": None,
            "lat": lat,
            "lon": lon,
            "category": None,
            "about": None,
            "rating": None,
            "rating_count": None,
            "price_level": None,
            "images": [],
            "phone": None,
            "website": None,
            "google_maps_url": None,
            "opening_hours": None,
            "comments": [],
            # Loại bỏ related_places
        }

        try:
            # === SMART SEARCH ===
            url, search_method = self._build_search_url(name, address, lat, lon, city, force_name_only)
            print(f"   [SEARCH] {search_method}")
            
            self.driver.get(url)
            time.sleep(4)

            current_url = self.driver.current_url
            result["google_maps_url"] = current_url

            # Handle chain/search results list
            if "/search/" in current_url or not re.search(r'/place/[^/]+/@', current_url):
                try:
                    wait = WebDriverWait(self.driver, 5)
                    links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href*='/place/']")))

                    if links:
                        best_score = 0
                        best_link = None
                        query_norm = normalize_place_name(name)

                        for link in links[:10]:
                            try:
                                href = link.get_attribute("href")
                                cand = extract_name_from_google_maps_url(href)
                                if cand:
                                    cand_norm = normalize_place_name(cand)
                                    score = max(fuzz.ratio(query_norm, cand_norm), fuzz.token_set_ratio(query_norm, cand_norm))
                                    if score > best_score:
                                        best_score = score
                                        best_link = link
                            except:
                                continue

                        if best_link and best_score >= 50:
                            best_link.click()
                            time.sleep(2.5)
                            result["google_maps_url"] = self.driver.current_url
                        elif links:
                            links[0].click()
                            time.sleep(2.5)
                            result["google_maps_url"] = self.driver.current_url
                except:
                    pass

            # === SCRAPE DATA TỪ TRANG CHÍNH ===
            
            rating, count = self._get_rating()
            result["rating"] = rating
            result["rating_count"] = count
            if rating:
                print(f"   [OK] Rating: {rating} ({count} reviews)")
            
            result["category"] = self._get_category()
            if result["category"]:
                print(f"   [OK] Category: {result['category']}")
            
            result["price_level"] = self._get_price_level()
            
            scraped_addr = self._get_address()

            # Validate địa chỉ scrape có khớp với địa chỉ gốc không
            if scraped_addr and not validate_address_match(address, scraped_addr):
                print(f"   [REJECT] Address mismatch:")
                print(f"      Original: {address[:50]}...")
                print(f"      Scraped:  {scraped_addr[:50]}...")
                result["new_address"] = None
            else:
                result["new_address"] = scraped_addr
                if scraped_addr:
                    print(f"   [OK] Address: {scraped_addr[:40]}...")
            
            result["phone"] = self._get_phone()
            if result["phone"]:
                print(f"   [OK] Phone: {result['phone']}")
            
            result["website"] = self._get_website()
            if result["website"]:
                print(f"   [OK] Website")
            
            # Opening hours
            result["opening_hours"] = self._get_hours()
            if result["opening_hours"]:
                print(f"   [OK] Hours: {len(result['opening_hours'])} days")
            
            # === SCRAPE DATA TỪ TABS ===
            
            result["images"] = self._get_images()
            print(f"   [OK] Images: {len(result['images'])}")
            
            result["about"] = self._get_about()
            if result["about"]:
                print(f"   [OK] About: {len(result['about'])} features")
            
            result["comments"] = self._get_comments(num_reviews)
            print(f"   [OK] Comments: {len(result['comments'])}")

        except Exception as e:
            print(f"   [ERROR] {e}")

        return result

    def get_related_names(self) -> List[str]:
        return self._get_related_place_names()

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


def scrape_csv_file(csv_file: str, output_file: str = None, headless: bool = True,
                    start_index: int = 0, end_index: int = None, city: str = DEFAULT_CITY,
                    expand_related: bool = False) -> List[dict]:
    """
    Scrape từ CSV file

    Args:
        csv_file: File CSV đầu vào (cần có: id/place_id, name, address, lat, lon)
        output_file: File JSON đầu ra
        headless: Chạy Chrome ẩn
        start_index: Bắt đầu từ index
        end_index: Kết thúc tại index
        city: Tên thành phố (dùng khi address không tốt)
        expand_related: Có mở rộng BFS không (mặc định False)
    """
    if output_file is None:
        name = os.path.splitext(os.path.basename(csv_file))[0]
        if end_index is not None:
            output_file = os.path.join(os.path.dirname(csv_file), f"{name}_scraped_{start_index}_{end_index}.json")
        elif start_index > 0:
            output_file = os.path.join(os.path.dirname(csv_file), f"{name}_scraped_from_{start_index}.json")
        else:
            output_file = os.path.join(os.path.dirname(csv_file), f"{name}_scraped.json")

    print("=" * 70)
    print("GOOGLE MAPS SCRAPER V5.7 - SMART SEARCH + BFS EXPANSION")
    print("=" * 70)
    print(f"Input: {csv_file}")
    print(f"Output: {output_file}")
    print(f"City fallback: {city}")
    print(f"Range: {start_index} -> {end_index or 'END'}")
    print(f"Expansion mode: {'ON - BFS expansion with related places' if expand_related else 'OFF'}")
    print("=" * 70)

    places = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Support both 'id' and 'place_id' columns
            place_id = row.get('place_id') or row.get('id', '')
            # Support both 'lng' and 'lon' columns
            lng_value = row.get('lng') or row.get('lon', 0)
            places.append({
                'place_id': place_id,
                'name': row.get('name', ''),
                'address': row.get('address', ''),
                'lat': float(row.get('lat', 0)),
                'lon': float(lng_value),
                'type': row.get('type', '')
            })

    if end_index is not None:
        places = places[start_index:end_index]
    else:
        places = places[start_index:]

    print(f"[OK] Loaded {len(places)} seed places")
    
    # Count places without good address
    no_addr_count = sum(1 for p in places if not is_valid_address(p['address']))
    print(f"[INFO] {no_addr_count} places without good address (will use name+city or coords)")
    print()

    scraper = GoogleMapsScraper(headless=headless, default_city=city)
    data = []

    try:
        if expand_related:
            # BFS Mode: Sử dụng queue để mở rộng
            queue = deque([(p, 0) for p in places])  # (place_dict, depth)
            visited = set()
            scraped_count = 0

            while queue and scraped_count < BFS_MAX_PLACES:
                current, depth = queue.popleft()
                name_norm = normalize_place_name(current['name'])
                key = name_norm  # Chỉ dùng name_norm để visited, vì related không có coords chính xác ban đầu

                if key in visited:
                    continue
                visited.add(key)

                print(f"\n[BFS Depth {depth} - {scraped_count + 1}] {current['name']}")
                print("-" * 50)

                try:
                    is_related = depth > 0  # Cho related places, force_name_only=True
                    result = scraper.scrape_place(
                        name=current['name'],
                        address=current['address'],
                        lat=current['lat'],
                        lon=current['lon'],
                        city=city,
                        get_related=False,  # Không cần get_related ở đây, sẽ gọi riêng
                        force_name_only=is_related
                    )
                    result['place_id'] = current['place_id']
                    result['type'] = current['type']
                    result['scraped_at'] = datetime.now().isoformat()
                    result['bfs_depth'] = depth  # Thêm depth để track
                    data.append(result)
                    scraped_count += 1

                    # Lấy related names nếu depth < max_depth
                    if depth < BFS_MAX_DEPTH:
                        print(f"   [EXPAND] Searching for related places...")
                        related_names = scraper.get_related_names()
                        print(f"   [OK] Related names: {len(related_names)} - {related_names}")
                        for rel_name in related_names:
                            rel_place = {
                                'place_id': '',  # Related chưa có id gốc
                                'name': rel_name,
                                'address': '',  # Không có address cho related
                                'lat': 0.0,  # Dummy lat/lon
                                'lon': 0.0,
                                'type': result['type']  # Kế thừa type từ parent
                            }
                            queue.append((rel_place, depth + 1))

                    # Auto-save every 10 places
                    if scraped_count % 10 == 0:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"\n[SAVE] {len(data)} places")
                except Exception as e:
                    print(f"[ERROR] {e}")
                    continue

        else:
            # Linear Mode: Scrape từng place độc lập
            for i, p in enumerate(places, 1):
                print(f"\n[{start_index + i}/{start_index + len(places)}] {p['name']}")
                print("-" * 50)

                try:
                    result = scraper.scrape_place(
                        name=p['name'],
                        address=p['address'],
                        lat=p['lat'],
                        lon=p['lon'],
                        city=city,
                        get_related=expand_related
                    )
                    result['place_id'] = p['place_id']
                    result['type'] = p['type']
                    result['scraped_at'] = datetime.now().isoformat()
                    data.append(result)

                    # Auto-save every 10 places
                    if i % 10 == 0:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"\n[SAVE] {len(data)} places")
                except Exception as e:
                    print(f"[ERROR] {e}")
                    continue

        # Final save
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*70}")
        print(f"[SUCCESS] {len(data)} places scraped")
        print(f"Output: {output_file}")
        print(f"{'='*70}")

        return data
    finally:
        scraper.close()


def merge_files(directory: str, output: str = None, pattern: str = "*_scraped_*.json"):
    import glob
    
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        print(f"No files found")
        return
    
    all_data = []
    for f in sorted(files):
        with open(f, 'r', encoding='utf-8') as file:
            file_data = json.load(file)
            all_data.extend(file_data)
            print(f"  {os.path.basename(f)}: {len(file_data)}")
    
    seen = set()
    unique = [x for x in all_data if x.get('place_id') not in seen and not seen.add(x.get('place_id'))]
    
    if output is None:
        output = os.path.join(directory, "merged.json")
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    print(f"\nMerged {len(unique)} places -> {output}")


def main():
    import sys
    
    # ============================================================
    # CẤU HÌNH - THAY ĐỔI THEO NHU CẦU
    # ============================================================
    csv_file = r"C:\HCMUS\ComputationalThinking\track-asia\test_museum.csv"  # CHANGE THIS
    city = "Đà Nẵng, Việt Nam"  # City fallback khi không có address
    # ============================================================
    
    if len(sys.argv) >= 2 and sys.argv[1] == '--help':
        print("""
GOOGLE MAPS SCRAPER V5.7 - SMART SEARCH + BFS EXPANSION

Usage:
    python scraper.py                      # Scrape toàn bộ file
    python scraper.py 10                   # Scrape 10 places đầu tiên
    python scraper.py 0 50                 # Scrape từ index 0 đến 50
    python scraper.py 50 100               # Scrape từ index 50 đến 100
    python scraper.py --expand             # Scrape toàn bộ + BFS expansion
    python scraper.py --expand 0 50        # Scrape 0-50 + BFS expansion
    python scraper.py merge [directory]    # Merge các file JSON

Search Strategy:
    1. name + address  (nếu address có đường, phường, quận...)
    2. name + city     (nếu address không đủ tốt)
    3. name @lat,lon   (fallback - chính xác nhất khi không có gì)
    - Cho related: Chỉ search bằng name (force_name_only=True)

BFS Expansion Mode (--expand):
    - Bắt đầu từ seed places trong CSV
    - Scrape và lấy tên related từ "Mọi người cũng tìm kiếm" qua aria-label trên div.Lnaw4c
    - Thêm related vào queue (chỉ name, search by name only), tránh duplicate bằng normalized name
    - Giới hạn: max {BFS_MAX_PLACES} places, max depth {BFS_MAX_DEPTH}
        """)
        return
    
    # Parse arguments
    expand_mode = False
    args = sys.argv[1:]

    # Check for --expand flag
    if '--expand' in args:
        expand_mode = True
        args = [a for a in args if a != '--expand']

    if len(sys.argv) >= 2 and sys.argv[1] == 'merge':
        merge_files(sys.argv[2] if len(sys.argv) >= 3 else os.path.dirname(csv_file))
    elif len(args) >= 2:
        scrape_csv_file(csv_file, headless=True,
                       start_index=int(args[0]),
                       end_index=int(args[1]),
                       city=city,
                       expand_related=expand_mode)
    elif len(args) == 1:
        scrape_csv_file(csv_file, headless=True,
                       start_index=0,
                       end_index=int(args[0]),
                       city=city,
                       expand_related=expand_mode)
    else:
        scrape_csv_file(csv_file, headless=False, city=city, expand_related=expand_mode)


if __name__ == "__main__":
    main()