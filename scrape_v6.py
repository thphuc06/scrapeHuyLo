# -*- coding: utf-8 -*-
"""
Google Maps Scraper V5.7.1 - SMART SEARCH + BFS EXPANSION + VERIFICATION
- Thêm location verification (coords distance + city validation)
- Giữ nguyên 100% logic cũ: BFS expansion, related places, search strategy
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
from math import radians, cos, sin, asin, sqrt
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
# CONFIGURATION
# ============================================================
DEFAULT_CITY = "Đà Nẵng, Việt Nam"
BFS_MAX_PLACES = 1000
BFS_MAX_DEPTH = 3
MAX_DISTANCE_KM = 50  # NEW: Max acceptable distance


# ============================================================
# NEW: VERIFICATION FUNCTIONS
# ============================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách giữa 2 coords (km)"""
    if not all([lat1, lon1, lat2, lon2]):
        return float('inf')
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    return 6371 * c


def extract_coords_from_url(url: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract lat, lon từ Google Maps URL"""
    if not url:
        return None, None
    
    try:
        match = re.search(r'/@(-?\d+\.?\d*),(-?\d+\.?\d*),\d+\.?\d*z', url)
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))
            return lat, lon
    except:
        pass
    
    return None, None


def extract_city_from_address(address: str) -> Optional[str]:
    """Extract tên thành phố từ địa chỉ"""
    if not address:
        return None
    
    addr_lower = unidecode(address.lower())
    
    cities = [
        'ha noi', 'thanh pho ho chi minh', 'ho chi minh', 'sai gon',
        'hai phong', 'da nang', 'can tho', 'bien hoa', 'vung tau',
        'nha trang', 'hue', 'nam dinh', 'hai duong', 'quang ninh',
        'thanh hoa', 'nghe an', 'dong nai', 'binh duong', 'long an',
        'khanh hoa', 'lam dong', 'bac ninh', 'thai nguyen', 'vinh phuc',
    ]
    
    for city in cities:
        if city in addr_lower:
            return city
    
    match = re.search(r'(?:thanh pho|tp\.?)\s+([a-z\s]+?)(?:,|$)', addr_lower)
    if match:
        return match.group(1).strip()
    
    return None


# ============================================================
# EXISTING FUNCTIONS (GIỮ NGUYÊN)
# ============================================================

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
    """Clean địa chỉ - loại bỏ rating, category"""
    if not addr or len(addr) < 5:
        return None
    
    invalid_patterns = [
        r'\d+[,.]?\d*\s*\(\d', r'·', r'Điểm thu hút', r'Điểm mốc',
        r'Đường đi', r'Mở cửa', r'Đóng cửa', r'Sắp đóng', r'Sắp mở',
        r'\bsao\b', r'\bstar\b', r'Khách sạn nghỉ', r'Bể bơi', r'Wi-Fi',
        r'Được tài trợ', r'Của Agoda', r'Booking\.com', r'Đại lý du lịch',
        r'Công viên xe', r'Phòng cho thuê',
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, addr, re.IGNORECASE):
            return None
    
    addr = re.sub(r'\s+', ' ', addr).strip()
    
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
    if not address:
        return False
    address = address.strip()
    if len(address) < 10:
        return False
    geo_keywords = ['đường', 'phố', 'quận', 'huyện', 'phường', 'xã',
                    'thành phố', 'việt nam', 'vietnam', ',']
    return any(kw in address.lower() for kw in geo_keywords)


def validate_address_match(original_address: str, scraped_address: str, 
                          original_city: str = None) -> bool:
    """
    Kiểm tra địa chỉ scrape có khớp với địa chỉ gốc không
    NEW: Thêm city validation
    """
    if not original_address or len(original_address.strip()) < 5:
        return True
    if not scraped_address:
        return True

    # === NEW: CHECK THÀNH PHỐ ===
    orig_city = extract_city_from_address(original_address)
    scrap_city = extract_city_from_address(scraped_address)
    
    if original_city:
        orig_city = extract_city_from_address(original_city) or orig_city
    
    if orig_city and scrap_city and orig_city != scrap_city:
        print(f"   [REJECT] City mismatch: '{orig_city}' vs '{scrap_city}'")
        return False

    # === EXISTING: CHECK SIMILARITY ===
    orig_norm = unidecode(original_address.lower()).strip()
    scrap_norm = unidecode(scraped_address.lower()).strip()

    if fuzz.partial_ratio(orig_norm, scrap_norm) >= 70:
        return True

    orig_words = set(orig_norm.split())
    scrap_words = set(scrap_norm.split())
    important_keywords = ['quan', 'phuong', 'duong', 'pho', 'xa', 'huyen',
                         'thanh pho', 'tinh', 'district', 'ward', 'street']
    
    orig_important = {w for w in orig_words if any(k in w for k in important_keywords)}
    scrap_important = {w for w in scrap_words if any(k in w for k in important_keywords)}

    if orig_important & scrap_important:
        return True
    
    if orig_important and scrap_important and not (orig_important & scrap_important):
        print(f"   [REJECT] Geographic keywords mismatch")
        return False

    common_words = ['viet', 'nam', 'vietnam', 'vn', 'so', 'number']
    meaningful_common = (orig_words & scrap_words) - set(common_words)
    
    return len(meaningful_common) >= 2


class GoogleMapsScraper:
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def __init__(self, headless: bool = True, default_city: str = DEFAULT_CITY):
        self.headless = headless
        self.driver = None
        self.default_city = default_city
        self.current_lat = None
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
        """Lấy About section"""
        features = []
        seen = set()
        
        try:
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
            
            try:
                scrollables = self.driver.find_elements(By.CSS_SELECTOR, "div[role='main'], div.m6QErb")
                for scrollable in scrollables:
                    for _ in range(5):
                        self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable)
                        time.sleep(0.3)
            except:
                pass
            
            def add_feature(aria: str):
                if not aria or len(aria) < 3 or len(aria) > 100:
                    return
                
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
                elif any(aria.startswith(x) for x in ["Picnic", "Wifi", "Toilet", "Restroom", "Parking", "Wheelchair"]):
                    feature = "Có: " + aria

                if feature and feature not in seen and len(feature) > 5:
                    seen.add(feature)
                    features.append(feature)
            
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
        """Lấy comments với full text"""
        comments = []
        try:
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "button[role='tab']")
            for tab in tabs:
                if any(x in tab.text.lower() for x in ["đánh giá", "review"]):
                    tab.click()
                    time.sleep(1.5)
                    break
            
            try:
                scrollable = self.driver.find_element(By.CSS_SELECTOR, "div[role='main']")
                for _ in range(3):
                    self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable)
                    time.sleep(0.5)
            except:
                pass
            
            try:
                more_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    "button.w8nwRe.kyuRq, button[aria-label='Xem thêm'], button[jsaction*='review.expandReview']")
                
                for btn in more_buttons:
                    try:
                        if btn.is_displayed():
                            btn_text = btn.text.strip().lower()
                            if btn_text in ['thêm', 'more', 'see more', 'xem thêm']:
                                btn.click()
                                time.sleep(0.3)
                    except:
                        continue
                
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
            
            time.sleep(0.5)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            review_divs = soup.find_all('div', {'data-review-id': True})
            
            seen = set()
            for div in review_divs:
                rid = div.get('data-review-id')
                if rid and rid not in seen:
                    seen.add(rid)
                    try:
                        author_elem = div.find('div', class_=lambda x: x and 'd4r55' in str(x))
                        author = author_elem.text.strip() if author_elem else "Anonymous"
                        
                        rating_elem = div.find('span', {'role': 'img', 'aria-label': True})
                        rating_text = rating_elem.get('aria-label', '') if rating_elem else ''
                        rating_match = re.search(r'(\d+)', rating_text)
                        rating = float(rating_match.group(1)) if rating_match else 0.0
                        
                        text_elem = div.find('span', class_=lambda x: x and 'wiI7pd' in str(x))
                        text = text_elem.text.strip() if text_elem else ""
                        
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
        """Lấy opening hours"""
        result = {}
        
        try:
            try:
                hour_btn = self.driver.find_element(By.CSS_SELECTOR, "button[data-item-id='oh']")
                if hour_btn.get_attribute("aria-expanded") != "true":
                    hour_btn.click()
                    time.sleep(1.2)
            except:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Đang mở'], button[aria-label*='Đã đóng']")
                    for btn in buttons:
                        btn.click()
                        time.sleep(1.2)
                        break
                except:
                    pass
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            table = soup.find('table', class_=lambda x: x and 'eK4R0e' in str(x))
            
            if table:
                rows = table.find_all('tr', class_=lambda x: x and 'y0skZc' in str(x))
                
                for row in rows:
                    day_td = row.find('td', class_=lambda x: x and 'ylH6lf' in str(x))
                    time_td = row.find('td', class_=lambda x: x and 'mxowUb' in str(x))
                    
                    if day_td and time_td:
                        day_name = day_td.get_text(strip=True)
                        hours_text = time_td.get('aria-label', '')
                        
                        if not hours_text:
                            li = time_td.find('li', class_=lambda x: x and 'G8aQO' in str(x))
                            if li:
                                hours_text = li.get_text(strip=True)
                        
                        if not hours_text:
                            hours_text = time_td.get_text(strip=True)
                        
                        if day_name and hours_text:
                            hours_text = hours_text.replace(' đến ', '-').replace('đến', '-').replace('–', '-')
                            result[day_name] = hours_text
            
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
        """Lấy tên các địa điểm liên quan từ 'Mọi người cũng tìm kiếm'"""
        related_names = []
        seen = set()

        try:
            try:
                scrollable = self.driver.find_element(By.CSS_SELECTOR, "div[role='main']")
                for _ in range(10):
                    self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable)
                    time.sleep(1.0)
            except:
                print("   [DEBUG] No scrollable div[role='main'] found.")
            
            time.sleep(3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            heading_pattern = re.compile(r'mọi người cũng tìm kiếm|people also search for', re.IGNORECASE)
            heading_elem = soup.find(string=heading_pattern)
            if heading_elem:
                print("   [DEBUG] Related section heading found: " + heading_elem.strip())
                section = heading_elem.find_parent('div', attrs={'role': 'region'}) or heading_elem.find_parent('div')
                if section:
                    print("   [DEBUG] Related section parent found.")
                else:
                    section = soup
            else:
                print("   [DEBUG] No related section heading found.")
                section = soup

            all_aria_elements = soup.find_all(attrs={'aria-label': True})
            print(f"   [DEBUG] Total elements with aria-label: {len(all_aria_elements)}")

            elements = section.find_all('div', class_=lambda x: x and 'lnaw4c' in str(x).lower())
            print(f"   [DEBUG] Number of divs with 'lnaw4c' in class: {len(elements)}")

            pattern = re.compile(r'.+ \d[.,]\d\s*sao\s*[-–\s]*[\d.,]+\s*đánh giá\s*gợi ý$', re.IGNORECASE)

            aria_samples = [elem.get('aria-label', '').strip() for elem in all_aria_elements[:10]]
            print("   [DEBUG] Sample aria-labels (top 10):")
            for sample in aria_samples:
                if sample:
                    print(f"     - {sample[:100]}...")

            for elem in elements:
                aria = elem.get('aria-label', '').strip()
                print(f"   [DEBUG] Aria-label found in Lnaw4c div: {aria[:100]}...")
                if pattern.match(aria):
                    print(f"   [DEBUG] Matched aria-label: {aria}")
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

        return list(seen)

    def _build_search_url(self, name: str, address: str, lat: float, lon: float, 
                        city: str = None, force_name_only: bool = False) -> Tuple[str, str]:
        """
        Tạo URL search thông minh - ƯU TIÊN COORDS
        Priority: name+address > name@coords > name+city
        """
        city = city or self.default_city
        
        if force_name_only:
            search_query = name
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}"
            return url, f"name_only: {search_query[:50]}..."
        
        # PRIORITY 1: Address đầy đủ (BEST)
        if is_valid_address(address):
            search_query = f"{name}, {address}"
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}"
            return url, f"name+addr: {search_query[:50]}..."
        
        # PRIORITY 2: Coords chính xác (BETTER) - NEW ORDER!
        if lat and lon and lat != 0 and lon != 0:
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(name)}/@{lat},{lon},17z"
            return url, f"name@coords: {name[:30]}... @{lat:.4f},{lon:.4f}"
        
        # PRIORITY 3: City fallback (LAST RESORT)
        if city:
            search_query = f"{name}, {city}"
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}"
            return url, f"name+city: {search_query[:50]}..."
        
        # Fallback cuối cùng: chỉ tên
        search_query = name
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(search_query)}"
        return url, f"name_only: {search_query[:50]}..."

    def scrape_place(self, name: str, address: str, lat: float, lon: float,
                     num_reviews: int = 3, city: str = None, get_related: bool = False,
                     force_name_only: bool = False) -> dict:
        """
        Scrape thông tin địa điểm từ Google Maps
        NEW: Thêm location verification
        """
        if not self.driver:
            self.init_driver()

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
        }

        try:
            url, search_method = self._build_search_url(name, address, lat, lon, city, force_name_only)
            print(f"   [SEARCH] {search_method}")
            
            self.driver.get(url)
            time.sleep(4)

            current_url = self.driver.current_url
            result["google_maps_url"] = current_url

            # === NEW: VERIFY COORDS ===
            scraped_lat, scraped_lon = extract_coords_from_url(current_url)
            if scraped_lat and scraped_lon and lat and lon:
                distance = haversine_distance(lat, lon, scraped_lat, scraped_lon)
                print(f"   [VERIFY] Distance: {distance:.2f}km")
                
                if distance > MAX_DISTANCE_KM:
                    print(f"   [REJECT] Too far from original location!")
                    print(f"      Original: {lat:.4f}, {lon:.4f}")
                    print(f"      Scraped:  {scraped_lat:.4f}, {scraped_lon:.4f}")
                    return result  # Return empty result

            # Handle chain/search results
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
                                    score = max(fuzz.ratio(query_norm, cand_norm), 
                                              fuzz.token_set_ratio(query_norm, cand_norm))
                                    if score > best_score:
                                        best_score = score
                                        best_link = link
                            except:
                                continue

                        if best_link and best_score >= 50:
                            best_link.click()
                            time.sleep(2.5)
                            result["google_maps_url"] = self.driver.current_url
                            
                            # === NEW: VERIFY COORDS AFTER CLICK ===
                            new_url = self.driver.current_url
                            new_lat, new_lon = extract_coords_from_url(new_url)
                            if new_lat and new_lon and lat and lon:
                                distance = haversine_distance(lat, lon, new_lat, new_lon)
                                print(f"   [VERIFY] After click distance: {distance:.2f}km")
                                if distance > MAX_DISTANCE_KM:
                                    print(f"   [REJECT] Clicked result too far!")
                                    return result
                        elif links:
                            links[0].click()
                            time.sleep(2.5)
                            result["google_maps_url"] = self.driver.current_url
                            
                            # === NEW: VERIFY COORDS FOR FIRST RESULT ===
                            new_url = self.driver.current_url
                            new_lat, new_lon = extract_coords_from_url(new_url)
                            if new_lat and new_lon and lat and lon:
                                distance = haversine_distance(lat, lon, new_lat, new_lon)
                                if distance > MAX_DISTANCE_KM:
                                    print(f"   [REJECT] First result too far!")
                                    return result
                except:
                    pass

            # === SCRAPE DATA ===
            
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

            # NEW: Validate với city check
            if scraped_addr and not validate_address_match(address, scraped_addr, city):
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
            
            result["opening_hours"] = self._get_hours()
            if result["opening_hours"]:
                print(f"   [OK] Hours: {len(result['opening_hours'])} days")
            
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
    GIỮ NGUYÊN LOGIC CŨ + THÊM VERIFICATION
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
    print("GOOGLE MAPS SCRAPER V5.7.1 - WITH VERIFICATION")
    print("=" * 70)
    print(f"Input: {csv_file}")
    print(f"Output: {output_file}")
    print(f"City fallback: {city}")
    print(f"Max distance: {MAX_DISTANCE_KM}km")
    print(f"Range: {start_index} -> {end_index or 'END'}")
    print(f"Expansion mode: {'ON - BFS expansion' if expand_related else 'OFF'}")
    print("=" * 70)

    places = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            place_id = row.get('place_id') or row.get('id', '')
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
    no_addr_count = sum(1 for p in places if not is_valid_address(p['address']))
    print(f"[INFO] {no_addr_count} places without good address\n")

    scraper = GoogleMapsScraper(headless=headless, default_city=city)
    data = []

    try:
        if expand_related:
            # BFS Mode - GIỮ NGUYÊN LOGIC CŨ
            queue = deque([(p, 0) for p in places])
            visited = set()
            scraped_count = 0

            while queue and scraped_count < BFS_MAX_PLACES:
                current, depth = queue.popleft()
                name_norm = normalize_place_name(current['name'])
                key = name_norm

                if key in visited:
                    continue
                visited.add(key)

                print(f"\n[BFS Depth {depth} - {scraped_count + 1}] {current['name']}")
                print("-" * 50)

                try:
                    is_related = depth > 0
                    result = scraper.scrape_place(
                        name=current['name'],
                        address=current['address'],
                        lat=current['lat'],
                        lon=current['lon'],
                        city=city,
                        get_related=False,
                        force_name_only=is_related
                    )
                    result['place_id'] = current['place_id']
                    result['type'] = current['type']
                    result['scraped_at'] = datetime.now().isoformat()
                    result['bfs_depth'] = depth
                    data.append(result)
                    scraped_count += 1

                    if depth < BFS_MAX_DEPTH:
                        print(f"   [EXPAND] Searching for related places...")
                        related_names = scraper.get_related_names()
                        print(f"   [OK] Related names: {len(related_names)} - {related_names}")
                        for rel_name in related_names:
                            rel_place = {
                                'place_id': '',
                                'name': rel_name,
                                'address': '',
                                'lat': 0.0,
                                'lon': 0.0,
                                'type': result['type']
                            }
                            queue.append((rel_place, depth + 1))

                    if scraped_count % 10 == 0:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"\n[SAVE] {len(data)} places")
                except Exception as e:
                    print(f"[ERROR] {e}")
                    continue

        else:
            # Linear Mode - GIỮ NGUYÊN LOGIC CŨ
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
    
    csv_file = r"C:\HCMUS\ComputationalThinking\track-asia\test_museum.csv"
    city = "Hồ Chí Minh, Việt Nam"
    
    if len(sys.argv) >= 2 and sys.argv[1] == '--help':
        print("""
GOOGLE MAPS SCRAPER V5.7.1 - WITH VERIFICATION

Usage:
    python scraper.py                      # Scrape toàn bộ file
    python scraper.py 10                   # Scrape 10 places đầu
    python scraper.py 0 50                 # Scrape từ 0-50
    python scraper.py --expand             # Scrape + BFS expansion
    python scraper.py merge [directory]    # Merge các file JSON

NEW: Location Verification
    - Extract coords từ Google Maps URL
    - Verify distance <= 50km
    - Reject nếu coords xa hoặc city khác
    - Check city trong địa chỉ

GIỮ NGUYÊN:
    - BFS expansion logic
    - Related places extraction
    - Search strategy order (name+addr -> name+city -> name+coords)
        """)
        return
    
    expand_mode = False
    args = sys.argv[1:]

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