import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

SHEET_NAME = 'Data Restoran Jakarta Barat'
JSON_KEYFILE = 'credentials.json'
TARGET_URL = "https://www.google.com/maps/search/restoran+di+jakarta+barat"

def setup_driver():
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def scrape_google_maps():
    driver = setup_driver()
    driver.get(TARGET_URL)
    time.sleep(5)
    
    print("Memulai pengguliran halaman untuk memuat semua data...")

    scrollable_div_xpath = '//div[contains(@aria-label, "Hasil untuk restoran di jakarta barat")]'

    try:
        scrollable_div = driver.find_element(By.XPATH, scrollable_div_xpath)
        for i in range(5):
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
            time.sleep(3)
    except Exception as e:
        print(f"Gagal melakukan scrolling otomatis: {e}")
        print("Lanjut mencoba mengambil data yang terlihat...")
        
    restaurants = []
    cards = driver.find_elements(By.CLASS_NAME, 'Nv2PK')

    print(f"Ditemukan {len(cards)} kartu restoran. Sedang memproses...")

    for card in cards:
        try:
            link_element = card.find_element(By.CLASS_NAME, 'hfpxzc')
            name = link_element.get_attribute('aria-label')
            link = link_element.get_attribute('href')
            
            try:
                rating = card.find_element(By.CLASS_NAME, 'MW4etd').text
            except:
                rating = "N/A"

            try:
                reviews = card.find_element(By.CLASS_NAME, 'UY7F9').text.replace('(', '').replace(')', '')
            except:
                reviews = "0"

            try:
                full_text = card.text.split('\n')
                metadata = full_text[1] if len(full_text) > 1 else ""
                
                parts = metadata.split('·')
                if len(parts) < 2:
                    parts = metadata.split('•')
                
                category = parts[1].strip() if len(parts) > 1 else "Unknown"
                price = next((s for s in parts if 'Rp' in s or '$' in s), "N/A")
                
            except:
                category = "Unknown"
                price = "N/A"

            restaurants.append({
                'Nama Restoran': name,
                'Rating': rating,
                'Review': reviews,
                'Kategori': category,
                'Harga': price,
                'Link Maps': link,
                'Status': 'Active'
            })
            
        except Exception:
            continue
    
    driver.quit()
    return pd.DataFrame(restaurants)

def clean_data(df):
    if df.empty:
        return df
        
    df = df.drop_duplicates(subset=['Nama Restoran'])
    df = df[df['Nama Restoran'] != '']
    df.reset_index(drop=True, inplace=True)
    return df

def upload_to_google_sheets(df):
    print("Menghubungkan ke Google Sheets...")

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
    client = gspread.authorize(creds)

    try:
        sheet = client.open(SHEET_NAME).sheet1
        sheet.clear()
        
        data_to_upload = [df.columns.tolist()] + df.values.tolist()
        
        sheet.update(range_name='A1', values=data_to_upload)

        print(f"Data mentah terupload. Sedang memformat tabel...")

        sheet.freeze(rows=1)
        
        header_range = f"A1:{chr(64 + len(df.columns))}1" 
        
        sheet.format(header_range, {
            "backgroundColor": {
                "red": 0.85,
                "green": 0.85,
                "blue": 0.85
            },
            "textFormat": {
                "bold": True,
                "fontSize": 11
            },
            "horizontalAlignment": "CENTER"
        })
        
        sheet.columns_auto_resize(0, len(df.columns) - 1)

        print(f"Sukses! {len(df)} data berhasil diupload dan diformat menjadi tabel.")

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: Sheet '{SHEET_NAME}' tidak ditemukan.")
    except Exception as e:
        print(f"Error upload/formatting: {e}")

if __name__ == "__main__":
    df_raw = scrape_google_maps()
    
    if not df_raw.empty:
        df_clean = clean_data(df_raw)
        print(df_clean.head())
        upload_to_google_sheets(df_clean)
    else:
        print("Tidak ada data yang berhasil diambil. Cek CSS Selector.")