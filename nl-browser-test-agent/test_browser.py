
from selenium import webdriver

driver = webdriver.Chrome()

try:
    driver.get("https://example.com")
    print("Title:", driver.title)
    print("URL:", driver.current_url)
finally:
    driver.quit()
