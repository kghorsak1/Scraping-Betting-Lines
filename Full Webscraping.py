"""
MASTER ODDS SCRIPT

This file combines all previously separate sportsbook scraping scripts (HardRock, BetMGM, Bet365, Caesars, ESPN)
plus an image overlay utility into one master file.

PRIMARY EDITS:
1) "Pick" Spread Workaround
   - We ensure that if any spread is "pick", "Pick", or "pk", it is standardized as "PK" to avoid errors.

2) Image Overlay Script Edits
   - Instead of individually overlaying text onto the image, we now produce a single table using `tabulate`
     and then overlay that table text onto the image.
   - Per requirement, HardRock data is shown on the far left (first columns in the table).
   - All website links and image file paths are placed at the top of the script for ease of use.
   - We unify the team names across all boxes to match whatever HardRock (the first box) reported (if HardRock
     is valid, otherwise we fall back to the next non-error site).
   - We shrink the width of the boxes by 20% but extend the (already shrunk) height an additional 20% so text
     no longer overflows.
   - The boxes have a light purple background.
"""

# ======================================================================
# =========================== GLOBAL SETTINGS ===========================
# ======================================================================

# -------------- URLs / FILE PATHS --------------
HARDROCK_URL = "https://app.hardrock.bet/home"
BETMGM_URL   = "https://sports.tn.betmgm.com/en/sports/basketball-7"
BET365_URL   = "https://www.bet365.com"
CAESARS_URL  = "https://sportsbook.caesars.com/us/ma/bet/"
ESPN_URL     = "https://espnbet.com/sport/basketball/organization/united-states/competition/nba"

# Image file path to use for the background of the table overlay
import random
import os
#DEFAULT_IMAGE_PATH = r"C:\Users\kghor\Downloads\AE.png"
# Define the folder path and image names
folder_path = r"C:\Users\kghor\OneDrive\Desktop\SportsBettingBackgrounds"
#image_files = ["AE.png", "HR.png", "Melo.png", "Sabonis.png"]
image_files =  ["Melo.png"]

# Randomly select an image and create the full path
DEFAULT_IMAGE_PATH = os.path.join(folder_path, random.choice(image_files))
OUTPUT_IMAGE_PATH  = "odds_overlay.png"

# ======================================================================
# ========================= HELPER FUNCTIONS ============================
# ======================================================================

import time
import random
import subprocess
import os
from datetime import datetime

from tabulate import tabulate
import pandas as pd

# ----------------- For HardRock and others using standard Selenium ----
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# -------------- For Caesar's (undetected-chromedriver) ----------------
import undetected_chromedriver as uc

# -------------- WebDriver manager + Chrome Options ---------------------
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# -------------- For the image overlay script --------------------------
from PIL import Image, ImageDraw, ImageFont

def sanitize_spread(spread_value: str) -> str:
    """
    Standardize any 'pick' or 'pk' spreads to 'PK' to avoid errors.
    """
    if not spread_value:
        return spread_value
    if spread_value.lower() in ["pick", "pk"]:
        return "PK"
    return spread_value


# ======================================================================
# =========================== HARDROCK CODE ============================
# ======================================================================

def hardrock_setup_driver():
    options = Options()
    options.add_argument('--start-maximized')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def hardrock_select_state(driver):
    try:
        wait = WebDriverWait(driver, 10)
        state_elements = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "state")))
        
        for state in state_elements:
            if "Tennessee" in state.text:
                state.click()
                time.sleep(3)
                return True
        return False
    except Exception as e:
        print(f"Error selecting state: {str(e)}")
        return False

def hardrock_select_nba(driver):
    """
    Example: If Hard Rock lists a 'NBA' tab with <p class="sport-tab-text">NBA</p>,
    we find and click it. Adjust if your site uses a different selector.
    """
    try:
        wait = WebDriverWait(driver, 10)
        nba_tab = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//p[@class='sport-tab-text' and text()='NBA']")
        ))
        nba_tab.click()
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Error selecting NBA tab: {str(e)}")
        return False

def hardrock_get_game_odds(team_name):
    """
    Scrape HardRock for a given team's upcoming game odds.
    Returns a standardized dictionary or an 'error' key if not found.
    """
    driver = None
    try:
        driver = hardrock_setup_driver()
        driver.get(HARDROCK_URL)

        if not hardrock_select_state(driver):
            return {"error": "Failed to select Tennessee state on HardRock"}
        if not hardrock_select_nba(driver):
            return {"error": "Failed to select NBA tab on HardRock"}
        
        time.sleep(5)  # Wait for games to load
        
        # 1) Find the market view containing team_name
        game_xpath = (
            f"//div[contains(@class, 'hr-market-view')]"
            f"//div[@class='show-for-medsmall' and contains(text(), '{team_name}')]"
        )
        game_element = driver.find_element(By.XPATH, game_xpath)
        
        market_view = game_element.find_element(
            By.XPATH, "ancestor::div[contains(@class,'hr-market-view')]"
        )
        
        # 2) Extract the two team names
        team_elements = market_view.find_elements(By.CLASS_NAME, "show-for-medsmall")
        if len(team_elements) < 2:
            return {"error": f"Could not find both teams in container for {team_name}."}
        team1_name = team_elements[0].text.strip()
        team2_name = team_elements[1].text.strip()
        
        # 3) Find columns
        columns = market_view.find_elements(
            By.XPATH, ".//div[@class='column small-8 selection-result']"
        )
        if len(columns) < 3:
            return {"error": f"Could not find all three odds columns for {team_name}."}
        
        # --- Spread ---
        spread_div = columns[0]
        spread_rows = spread_div.find_elements(
            By.XPATH, ".//div[contains(@class,'selection-container-vertical')]"
        )
        team1_spread = spread_rows[0].find_element(
            By.XPATH, ".//div[contains(@class,'selection-line-value')]"
        ).text.strip()
        team1_spread_odds = spread_rows[0].find_element(
            By.XPATH, ".//div[contains(@class,'selection-odds')]"
        ).text.strip()
        
        team2_spread = spread_rows[1].find_element(
            By.XPATH, ".//div[contains(@class,'selection-line-value')]"
        ).text.strip()
        team2_spread_odds = spread_rows[1].find_element(
            By.XPATH, ".//div[contains(@class,'selection-odds')]"
        ).text.strip()

        # Sanitize "pick" spreads
        team1_spread = sanitize_spread(team1_spread)
        team2_spread = sanitize_spread(team2_spread)
        
        # --- Total ---
        total_div = columns[1]
        total_rows = total_div.find_elements(
            By.XPATH, ".//div[contains(@class,'selection-container-vertical')]"
        )
        over_value = total_rows[0].find_element(
            By.XPATH, ".//div[contains(@class,'selection-line-value')]"
        ).text.strip()
        over_odds = total_rows[0].find_element(
            By.XPATH, ".//div[contains(@class,'selection-odds')]"
        ).text.strip()
        
        under_value = total_rows[1].find_element(
            By.XPATH, ".//div[contains(@class,'selection-line-value')]"
        ).text.strip()
        under_odds = total_rows[1].find_element(
            By.XPATH, ".//div[contains(@class,'selection-odds')]"
        ).text.strip()
        
        # --- Moneyline ---
        money_div = columns[2]
        money_rows = money_div.find_elements(
            By.XPATH, ".//div[contains(@class,'selection-container-vertical')]"
        )
        team1_money = money_rows[0].find_element(
            By.XPATH, ".//div[contains(@class,'selection-odds')]"
        ).text.strip()
        team2_money = money_rows[1].find_element(
            By.XPATH, ".//div[contains(@class,'selection-odds')]"
        ).text.strip()
        
        return {
            "team1_name": team1_name,
            "team1_spread": team1_spread,
            "team1_spread_odds": team1_spread_odds,
            "team1_over": over_value,   # e.g., O 220.5
            "team1_over_odds": over_odds,
            "team1_under": under_value, # e.g., U 220.5
            "team1_under_odds": under_odds,
            "team1_moneyline": team1_money,

            "team2_name": team2_name,
            "team2_spread": team2_spread,
            "team2_spread_odds": team2_spread_odds,
            "team2_over": over_value,
            "team2_over_odds": over_odds,
            "team2_under": under_value,
            "team2_under_odds": under_odds,
            "team2_moneyline": team2_money
        }
        
    except Exception as e:
        return {"error": f"HardRock error for {team_name}: {str(e)}"}
    finally:
        if driver:
            driver.quit()


# ======================================================================
# ============================= BETMGM CODE ============================
# ======================================================================

def betmgm_setup_driver():
    """
    Setup Chrome driver for BetMGM.
    """
    chrome_options = Options()
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def betmgm_get_game_odds(team_name):
    """
    New BetMGM code.
    Returns a standardized dictionary with odds or an error message.
    """
    driver = betmgm_setup_driver()
    try:
        driver.get(BETMGM_URL)
        
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "grid-event-wrapper")))
        
        time.sleep(2)

        xpath = f"//div[contains(@class, 'grid-event-wrapper')]//div[contains(text(), '{team_name}')]"
        game_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

        game_container = game_element.find_element(
            By.XPATH, "./ancestor::div[contains(@class, 'grid-event-wrapper')]"
        )

        # Team names
        team1_name = game_container.find_element(
            By.XPATH, ".//div[@class='participant']"
        ).text.strip()
        team2_name = game_container.find_elements(
            By.XPATH, ".//div[@class='participant']"
        )[1].text.strip()

        # For spread values
        spread_elements = game_container.find_elements(
            By.XPATH,
            ".//div[contains(@class, 'option-attribute') and not(contains(@class, 'small-font'))]"
        )
        team1_spread = spread_elements[0].text.strip()
        team2_spread = spread_elements[1].text.strip()
        team1_spread = sanitize_spread(team1_spread)
        team2_spread = sanitize_spread(team2_spread)

        # For total points
        total_elements = game_container.find_elements(
            By.XPATH,
            ".//div[contains(@class, 'option-attribute small-font')]"
        )
        team1_total = total_elements[0].text.strip()  # e.g. "O 236.5"
        team2_total = total_elements[1].text.strip()  # e.g. "U 236.5"

        # Get spread odds (the first ms-option-group contains 2 spread odds)
        spread_odds = game_container.find_elements(
            By.XPATH,
            ".//ms-option-group[contains(@class, 'two-column')]//span[contains(@class, 'custom-odds-value-style')]"
        )
        team1_spread_odds = spread_odds[0].text.strip()
        team2_spread_odds = spread_odds[1].text.strip()

        # Get total odds (the next ms-option-group often has the totals)
        total_odds = game_container.find_elements(
            By.XPATH,
            ".//ms-option-group[not(contains(@class, 'two-column'))]//span[contains(@class, 'custom-odds-value-style')]"
        )
        # Adjust indexing from new code snippet to match correct Over/Under location
        total_over_odds = total_odds[1].text.strip()
        total_under_odds = total_odds[2].text.strip()

        # Get moneyline odds (last ms-option-group)
        money_odds = game_container.find_elements(
            By.XPATH,
            ".//ms-option-group[last()]//span[contains(@class, 'custom-odds-value-style')]"
        )
        team1_money = money_odds[0].text.strip()
        team2_money = money_odds[1].text.strip()

        # Return in the same structure the master script uses:
        return {
            "team1_name": team1_name,
            "team1_spread": team1_spread,
            "team1_spread_odds": team1_spread_odds,
            "team1_over": team1_total,      # e.g. "O 236.5"
            "team1_over_odds": total_over_odds,
            "team1_under": team1_total.replace("O ", "U "),  # quick hack if "O " is present
            "team1_under_odds": total_under_odds,
            "team1_moneyline": team1_money,
            
            "team2_name": team2_name,
            "team2_spread": team2_spread,
            "team2_spread_odds": team2_spread_odds,
            "team2_over": team2_total,      # e.g. "U 236.5"
            "team2_over_odds": total_under_odds,
            "team2_under": team2_total.replace("U ", "O "),  # quick hack if "U " is present
            "team2_under_odds": total_over_odds,
            "team2_moneyline": team2_money
        }

    except TimeoutException:
        return {'error': f'BetMGM Timeout waiting for {team_name} odds to load'}
    except NoSuchElementException as e:
        return {'error': f'BetMGM NoSuchElement: {str(e)}'}
    except Exception as e:
        return {'error': f'BetMGM error for {team_name}: {str(e)}'}
    finally:
        time.sleep(1)
        driver.quit()


# ======================================================================
# ============================= BET365 CODE ============================
# ======================================================================

def bet365_setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def bet365_accept_cookies_if_present(driver):
    """
    Attempt to accept cookies on Bet365 if a popup is present.
    """
    try:
        wait = WebDriverWait(driver, 10)
        accept_xpath = "//div[contains(@class,'ccm-CookieConsentPopup_Accept') and contains(text(),'Accept All')]"
        accept_button = wait.until(EC.element_to_be_clickable((By.XPATH, accept_xpath)))
        accept_button.click()
        time.sleep(2)
    except Exception as e:
        # No cookie popup or couldn't click 'Accept All'
        pass

def bet365_get_full_team_name(driver, team_name):
    """
    Find the full team name (e.g., 'BOS Celtics' from partial 'Celtics')
    if the Bet365 listing includes extra text. Otherwise, returns the same team_name.
    """
    try:
        team_xpath = (
            f"//div[contains(@class, 'cpm-ParticipantFixtureDetailsBasketball_Team') and contains(text(), '{team_name}')]"
        )
        team_element = driver.find_element(By.XPATH, team_xpath)
        return team_element.text
    except:
        return team_name

def bet365_find_team_spread(driver, team_name):
    wait = WebDriverWait(driver, 10)
    try:
        full_team_name = bet365_get_full_team_name(driver, team_name)
        
        # Find the spread element for our team
        spread_element = wait.until(
            EC.presence_of_element_located((
                By.XPATH,
                f"//div[contains(@class, 'cpm-ParticipantOdds') and contains(@aria-label, '{full_team_name}') and contains(@aria-label, 'Spread')]"
            ))
        )
        
        # Team spread and odds
        handicap = spread_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Handicap").text
        odds = spread_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Odds").text
        handicap = sanitize_spread(handicap)

        aria_label = spread_element.get_attribute("aria-label")
        try:
            opp_name = aria_label.split(" v ")[1].split(" Spread")[0]
        except:
            opp_name = "Opponent"

        # Opponent's spread element
        opp_spread_element = spread_element.find_element(
            By.XPATH,
            "following-sibling::div[contains(@class, 'cpm-ParticipantOdds')][1]"
        )
        opp_handicap = opp_spread_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Handicap").text
        opp_odds = opp_spread_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Odds").text
        opp_handicap = sanitize_spread(opp_handicap)

        return {
            "team_name": full_team_name,
            "team_spread": handicap,
            "team_spread_odds": odds,
            "opp_name": opp_name,
            "opp_spread": opp_handicap,
            "opp_spread_odds": opp_odds
        }
    except Exception as e:
        return {"error": f"Spread not found: {str(e)}"}

def bet365_find_team_total(driver, team_name):
    wait = WebDriverWait(driver, 10)
    try:
        full_team_name = bet365_get_full_team_name(driver, team_name)
        
        over_element = wait.until(
            EC.presence_of_element_located((
                By.XPATH,
                f"//div[contains(@class, 'cpm-ParticipantOdds') and contains(@aria-label, '{full_team_name}') and contains(@aria-label, 'Total')]"
            ))
        )
        over_handicap = over_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Handicap").text
        over_odds = over_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Odds").text

        parts = over_handicap.split(" ")
        if len(parts) >= 2:
            total_value = parts[1]
        else:
            total_value = over_handicap

        under_element = over_element.find_element(
            By.XPATH,
            "following-sibling::div[contains(@class, 'cpm-ParticipantOdds')][1]"
        )
        under_odds = under_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Odds").text.strip()
        
        return {
            "team_name": full_team_name,
            "total_value": total_value,
            "over_odds": over_odds,
            "under_odds": under_odds
        }
    except Exception as e:
        return {"error": f"Total not found: {str(e)}"}

def bet365_find_team_moneyline(driver, team_name):
    wait = WebDriverWait(driver, 10)
    try:
        full_team_name = bet365_get_full_team_name(driver, team_name)
        
        ml_xpath = (
            f"//div[contains(@class, 'cpm-ParticipantOdds') and contains(@class, 'cpm-ParticipantOddsOnly50') "
            f"and contains(@aria-label, '{full_team_name}') and contains(@aria-label, 'Money')]"
        )
        ml_element = wait.until(EC.presence_of_element_located((By.XPATH, ml_xpath)))
        
        team_odds = ml_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Odds").text.strip()

        aria_label = ml_element.get_attribute("aria-label")
        try:
            opp_name = aria_label.split(" v ")[1].split(" Money")[0]
        except:
            opp_name = "Opponent"

        opp_element = ml_element.find_element(
            By.XPATH,
            "following-sibling::div[contains(@class, 'cpm-ParticipantOdds')][1]"
        )
        opp_odds = opp_element.find_element(By.CLASS_NAME, "cpm-ParticipantOdds_Odds").text.strip()

        return {
            "team_name": full_team_name,
            "team_money": team_odds,
            "opp_name": opp_name,
            "opp_money": opp_odds
        }
    except Exception as e:
        return {"error": f"Moneyline not found: {str(e)}"}

def bet365_get_game_odds(team_name):
    """
    Bet365 code integrated into the master script.
    Returns a standardized dictionary with odds or an error message.
    """
    driver = None
    try:
        driver = bet365_setup_driver()
        driver.get(BET365_URL)
        time.sleep(5)

        bet365_accept_cookies_if_present(driver)
        time.sleep(5)

        spread_data = bet365_find_team_spread(driver, team_name)
        total_data = bet365_find_team_total(driver, team_name)
        money_data = bet365_find_team_moneyline(driver, team_name)

        if "error" in spread_data:
            return {"error": spread_data["error"]}
        if "error" in total_data:
            return {"error": total_data["error"]}
        if "error" in money_data:
            return {"error": money_data["error"]}

        t1_name = spread_data["team_name"]
        t2_name = spread_data["opp_name"]

        return {
            "team1_name": t1_name,
            "team1_spread": spread_data["team_spread"],
            "team1_spread_odds": spread_data["team_spread_odds"],
            "team1_over": f"O {total_data['total_value']}",
            "team1_over_odds": total_data["over_odds"],
            "team1_under": f"U {total_data['total_value']}",
            "team1_under_odds": total_data["under_odds"],
            "team1_moneyline": money_data["team_money"],

            "team2_name": t2_name,
            "team2_spread": spread_data["opp_spread"],
            "team2_spread_odds": spread_data["opp_spread_odds"],
            "team2_over": f"O {total_data['total_value']}",
            "team2_over_odds": total_data["over_odds"],
            "team2_under": f"U {total_data['total_value']}",
            "team2_under_odds": total_data["under_odds"],
            "team2_moneyline": money_data["opp_money"]
        }

    except Exception as e:
        return {"error": f"Bet365 error for {team_name}: {str(e)}"}
    finally:
        if driver:
            driver.quit()


# ======================================================================
# ============================= CAESARS CODE ===========================
# ======================================================================

def get_chrome_version():
    """Try to detect local Chrome version (Windows + Linux)."""
    try:
        process = subprocess.Popen(
            'reg query "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon" /v version',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output, error = process.communicate()
        version = output.decode('utf-8').strip().split()[-1]
        return int(version.split('.')[0])
    except:
        # Fallback: try google-chrome --version
        try:
            process = subprocess.Popen(
                ['google-chrome', '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = process.communicate()
            version = output.decode('utf-8').strip().split()[-1]
            return int(version.split('.')[0])
        except:
            return None

def caesars_setup_driver():
    """Setup undetected-chromedriver with version compatibility."""
    try:
        options = uc.ChromeOptions()
        options.add_argument('--window-size=1920,1080')
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        options.add_experimental_option("prefs", prefs)
        
        driver = uc.Chrome(
            options=options,
            driver_executable_path=None,
            suppress_welcome=True,
            version_main=132  # Update if needed
        )
        return driver
    except Exception as e:
        print(f"Error setting up driver (main version approach): {str(e)}")
        print("Trying alternative setup for undetected_chromedriver...")
        try:
            options = uc.ChromeOptions()
            options.add_argument('--window-size=1920,1080')
            driver = uc.Chrome(options=options, use_subprocess=True, suppress_welcome=True)
            return driver
        except Exception as e2:
            print(f"Alternative setup failed: {str(e2)}")
            raise

def random_sleep(min_t=1, max_t=3):
    time.sleep(random.uniform(min_t, max_t))

def caesars_get_full_team_name(driver, team_name):
    try:
        team_xpath = f"//div[contains(@class, 'heading-md')]//span[contains(text(), '{team_name}')]"
        team_element = driver.find_element(By.XPATH, team_xpath)
        return team_element.text.strip()
    except:
        return team_name

def caesars_find_team_spread(driver, team_name):
    """Spread function with 'pick' => 'PK' workaround."""
    wait = WebDriverWait(driver, 10)
    try:
        full_team_name = caesars_get_full_team_name(driver, team_name)
        
        spread_xpath = f"//button[contains(@aria-label, '{full_team_name}') and contains(@aria-label, 'odds')]"
        spread_button = wait.until(EC.presence_of_element_located((By.XPATH, spread_xpath)))
        
        try:
            line_element = spread_button.find_element(By.CLASS_NAME, "cui__market-button-line")
            team_line = line_element.text.strip()
        except:
            team_line = "PK"
        team_line = sanitize_spread(team_line)
        
        odds_element = spread_button.find_element(By.CLASS_NAME, "cui-text-fg-primary")
        team_odds = odds_element.text.strip()
        
        market_id = spread_button.get_attribute("data-market")
        opp_xpath = f"//button[@data-market='{market_id}' and not(contains(@aria-label, '{full_team_name}'))]"
        opp_button = driver.find_element(By.XPATH, opp_xpath)
        
        try:
            opp_line_el = opp_button.find_element(By.CLASS_NAME, "cui__market-button-line")
            opp_line = opp_line_el.text.strip()
        except:
            opp_line = "PK"
        opp_line = sanitize_spread(opp_line)
        
        opp_odds_el = opp_button.find_element(By.CLASS_NAME, "cui-text-fg-primary")
        opp_odds = opp_odds_el.text.strip()
        
        return {
            "team_line": team_line,
            "team_odds": team_odds,
            "opp_line": opp_line,
            "opp_odds": opp_odds,
            "team_name": full_team_name
        }
    except Exception as e:
        return {"error": f"Caesars spread not found: {str(e)}"}

def caesars_find_team_total(driver, team_name):
    """
    Find total (over/under) for a specific team's game. Uses same logic as universal scraper.
    """
    wait = WebDriverWait(driver, 10)
    try:
        full_team_name = caesars_get_full_team_name(driver, team_name)
        print(f"Debug: Looking for total for team: {full_team_name}")
        
        # Try multiple possible spread button XPaths
        spread_xpaths = [
            f"//button[contains(@aria-label, '{full_team_name}') and contains(@aria-label, 'Spread')]",
            f"//button[contains(@aria-label, 'Spread') and contains(@aria-label, '{full_team_name}')]",
            f"//button[contains(@aria-label, '{full_team_name}')]"
        ]
        
        spread_button = None
        for xpath in spread_xpaths:
            print(f"Debug: Trying spread xpath: {xpath}")
            try:
                spread_button = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                if spread_button:
                    print(f"Debug: Found spread button with aria-label: {spread_button.get_attribute('aria-label')}")
                    break
            except:
                continue
                
        if not spread_button:
            raise Exception(f"Could not find spread button for {full_team_name}")
            
        event_id = spread_button.get_attribute("data-event")
        print(f"Debug: Found event ID: {event_id}")
        
        # Print all totals for this event to verify
        total_buttons = driver.find_elements(By.XPATH, f"//button[@data-event='{event_id}' and contains(@aria-label, 'Total Points')]")
        print(f"Debug: Found {len(total_buttons)} total buttons for this event")
        for btn in total_buttons:
            print(f"Debug: Total button aria-label: {btn.get_attribute('aria-label')}")
        
        # Now find the over button for this event
        over_xpath = f"//button[@data-event='{event_id}' and contains(@aria-label, 'Total Points') and contains(@aria-label, 'over')]"
        print(f"Debug: Searching for over button with xpath: {over_xpath}")
        over_button = wait.until(EC.presence_of_element_located((By.XPATH, over_xpath)))
        print(f"Debug: Found over button with aria-label: {over_button.get_attribute('aria-label')}")
        
        # Get the total and odds from the Over button
        line_element = over_button.find_element(By.CLASS_NAME, "cui__market-button-line")
        odds_element = over_button.find_element(By.CLASS_NAME, "cui-text-fg-primary")
        
        total_value = line_element.text
        over_odds = odds_element.text
        print(f"Debug: Found total value: {total_value}, over odds: {over_odds}")
        
        # Find the Under button using the same market ID
        market_id = over_button.get_attribute("data-market")
        under_xpath = f"//button[@data-market='{market_id}' and contains(@aria-label, 'under')]"
        under_button = driver.find_element(By.XPATH, under_xpath)
        
        # Get the under odds
        under_odds = under_button.find_element(By.CLASS_NAME, "cui-text-fg-primary").text
        print(f"Debug: Found under odds: {under_odds}")
        
        # Return in caesars format
        return {
            "total_value": total_value,
            "over_odds": over_odds,
            "under_odds": under_odds
        }
        
    except Exception as e:
        print(f"Debug ERROR: Exception occurred")
        print(f"Debug ERROR: Exception type: {type(e).__name__}")
        print(f"Debug ERROR: Exception message: {str(e)}")
        # Print all buttons for debugging
        print("Debug ERROR: Listing all buttons with Total Points in aria-label:")
        try:
            all_total_buttons = driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Total Points')]")
            for btn in all_total_buttons:
                print(f"Button aria-label: {btn.get_attribute('aria-label')}")
                print(f"Button data-event: {btn.get_attribute('data-event')}")
        except:
            print("Could not list total buttons")
        return {"error": f"Caesars total not found: {str(e)}"}

def caesars_find_team_moneyline(driver, team_name):
    wait = WebDriverWait(driver, 10)
    try:
        full_team_name = caesars_get_full_team_name(driver, team_name)
        print(f"Debug: Looking for moneyline for team: {full_team_name}")
        
        # Wait for page load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1)  # Small buffer for dynamic content
        
        # Try multiple possible moneyline XPaths
        ml_xpaths = [
            f"//button[contains(@aria-label, '{full_team_name}') and not(contains(@aria-label, 'line')) and not(contains(@aria-label, 'total'))]",
            f"//button[contains(@aria-label, '{full_team_name}') and contains(@aria-label, 'Money')]",
            f"//button[contains(@aria-label, 'Money') and contains(@aria-label, '{full_team_name}')]"
        ]
        
        ml_button = None
        for xpath in ml_xpaths:
            print(f"Debug: Trying moneyline xpath: {xpath}")
            try:
                ml_button = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                if ml_button:
                    print(f"Debug: Found moneyline button with aria-label: {ml_button.get_attribute('aria-label')}")
                    break
            except:
                continue
                
        if not ml_button:
            raise Exception(f"Could not find moneyline button for {full_team_name}")
        
        # Add retry logic for finding odds
        max_retries = 3
        team_odds = None
        for attempt in range(max_retries):
            try:
                odds_element = ml_button.find_element(By.CLASS_NAME, "cui-text-fg-primary")
                team_odds = odds_element.text.strip()
                print(f"Debug: Found team odds: {team_odds}")
                break
            except:
                print(f"Debug: Retry {attempt + 1} getting team odds")
                time.sleep(1)
                
        if not team_odds:
            raise Exception("Could not find team odds")
            
        # Get market ID and find opponent button
        market_id = ml_button.get_attribute("data-market")
        print(f"Debug: Found market ID: {market_id}")
        
        opp_xpath = f"//button[@data-market='{market_id}' and not(contains(@aria-label, '{full_team_name}'))]"
        print(f"Debug: Searching for opponent button with xpath: {opp_xpath}")
        
        # Add retry logic for opponent odds
        opp_button = None
        opp_odds = None
        for attempt in range(max_retries):
            try:
                opp_button = driver.find_element(By.XPATH, opp_xpath)
                print(f"Debug: Found opponent button with aria-label: {opp_button.get_attribute('aria-label')}")
                odds_element = opp_button.find_element(By.CLASS_NAME, "cui-text-fg-primary")
                opp_odds = odds_element.text.strip()
                print(f"Debug: Found opponent odds: {opp_odds}")
                break
            except:
                print(f"Debug: Retry {attempt + 1} getting opponent odds")
                time.sleep(1)
                
        if not opp_odds:
            raise Exception("Could not find opponent odds")
        
        return {
            "team_moneyline": team_odds,
            "opp_moneyline": opp_odds,
            "team_name": full_team_name
        }
        
    except Exception as e:
        print(f"Debug ERROR: Exception occurred")
        print(f"Debug ERROR: Exception type: {type(e).__name__}")
        print(f"Debug ERROR: Exception message: {str(e)}")
        # Print all buttons for debugging
        print("Debug ERROR: Listing all relevant buttons:")
        try:
            all_buttons = driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Money')]")
            for btn in all_buttons:
                print(f"Button aria-label: {btn.get_attribute('aria-label')}")
                print(f"Button data-market: {btn.get_attribute('data-market')}")
        except:
            print("Could not list buttons")
        return {"error": f"Caesars moneyline not found: {str(e)}"}

def caesars_get_game_odds(team_name):
    """
    Use undetected_chromedriver to scrape Caesars for the given team_name.
    Returns a standardized dictionary or an error key if not found.
    """
    driver = None
    try:
        _ = get_chrome_version()  # Attempt detection

        driver = caesars_setup_driver()
        driver.get(CAESARS_URL)
        random_sleep(4, 6)
        
        # Attempt to click NBA tab (may or may not exist)
        try:
            nba_tab = driver.find_element(By.XPATH, "//div[contains(text(), 'NBA')]")
            nba_tab.click()
            random_sleep()
        except:
            pass  # NBA tab not found or maybe already selected.
        
        driver.execute_script("window.scrollTo(0, 300);")
        random_sleep()
        
        spread_data = caesars_find_team_spread(driver, team_name)
        total_data = caesars_find_team_total(driver, team_name)
        money_data = caesars_find_team_moneyline(driver, team_name)
        
        if "error" in spread_data or "error" in total_data or "error" in money_data:
            err_msg = spread_data.get("error") or total_data.get("error") or money_data.get("error")
            return {"error": err_msg or f"Caesars partial data error for {team_name}"}
        
        t1_name = spread_data["team_name"]
        total_val = total_data["total_value"]
        
        return {
            "team1_name": t1_name,
            "team1_spread": spread_data["team_line"],
            "team1_spread_odds": spread_data["team_odds"],
            "team1_over": f"O {total_val}",
            "team1_over_odds": total_data["over_odds"],
            "team1_under": f"U {total_val}",
            "team1_under_odds": total_data["under_odds"],
            "team1_moneyline": money_data["team_moneyline"],
            
            "team2_name": "Opponent?",  # We haven't extracted actual opponent name from these lumps
            "team2_spread": spread_data["opp_line"],
            "team2_spread_odds": spread_data["opp_odds"],
            "team2_over": f"O {total_val}",
            "team2_over_odds": total_data["over_odds"],
            "team2_under": f"U {total_val}",
            "team2_under_odds": total_data["under_odds"],
            "team2_moneyline": money_data["opp_moneyline"]
        }
    except Exception as e:
        return {"error": f"Caesars error for {team_name}: {str(e)}"}
    finally:
        if driver:
            random_sleep(1,2)
            driver.quit()


# ======================================================================
# ============================== ESPN CODE =============================
# ======================================================================

def espn_setup_driver():
    """
    Sets up the Chrome WebDriver for ESPN scraping.
    """
    options = Options()
    options.add_argument('--start-maximized')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def espn_accept_cookies(driver):
    """
    Accept cookies on the ESPNBet website using the ID selector, if present.
    """
    try:
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        button.click()
        return True
    except:
        return False

def espn_get_game_odds(team_name):
    """
    Updated ESPN scraping function (debugging removed). 
    Returns a dictionary with standardized keys or 'error' if not found.
    """
    driver = None
    try:
        driver = espn_setup_driver()
        driver.get(ESPN_URL)
        
        # Attempt to accept cookies; failure won't stop the script
        espn_accept_cookies(driver)
        
        # Give the page some time to load
        time.sleep(5)
        
        # Locate game container by partial team text
        game_containers = driver.find_elements(
            By.XPATH,
            f"//div[contains(@class, 'text-style-s-medium text-primary') and contains(text(), '{team_name}')]"
        )
        if not game_containers:
            return {"error": f"ESPN: Could not find game container for {team_name}"}
        
        # Grab the parent container for the first match
        game_element = game_containers[0].find_element(
            By.XPATH,
            "ancestor::div[contains(@id, 'default|')]"
        )
        
        # Extract team names
        team_elements = game_element.find_elements(
            By.XPATH,
            ".//div[contains(@class, 'text-style-s-medium text-primary')]"
        )
        if len(team_elements) < 2:
            return {"error": "ESPN: Could not find both team names"}
        
        team1_name = team_elements[0].text.strip()
        team2_name = team_elements[1].text.strip()
        
        def extract_button_info(button):
            # Try to get line/spread or over/under
            try:
                line_el = button.find_element(
                    By.XPATH,
                    ".//span[contains(@class, 'text-selector-label-deselected')]"
                )
                line_val = line_el.text.strip()
            except:
                line_val = None
            
            # Try to get odds
            try:
                odds_el = button.find_element(
                    By.XPATH,
                    ".//span[contains(@class, 'text-style-xs-bold')]"
                )
                odds_val = odds_el.text.strip()
            except:
                odds_val = None
            
            return line_val, odds_val
        
        # Spread
        spread_buttons = game_element.find_elements(
            By.XPATH,
            ".//button[contains(@data-type, '_SPREAD')]"
        )
        if len(spread_buttons) < 2:
            return {"error": "ESPN: Could not find spread information"}
        
        team1_spread, team1_spread_odds = extract_button_info(spread_buttons[0])
        team2_spread, team2_spread_odds = extract_button_info(spread_buttons[1])
        team1_spread = sanitize_spread(team1_spread)
        team2_spread = sanitize_spread(team2_spread)
        
        # Total
        total_buttons = game_element.find_elements(
            By.XPATH,
            ".//button[contains(@data-type, 'OVER') or contains(@data-type, 'UNDER')]"
        )
        if len(total_buttons) < 2:
            return {"error": "ESPN: Could not find total information"}
        
        over_value, over_odds = extract_button_info(total_buttons[0])
        under_value, under_odds = extract_button_info(total_buttons[1])
        
        # Moneyline
        moneyline_buttons = game_element.find_elements(
            By.XPATH,
            ".//button[contains(@data-type, '_MONEYLINE')]"
        )
        if len(moneyline_buttons) < 2:
            return {"error": "ESPN: Could not find moneyline information"}
        
        _, team1_ml = extract_button_info(moneyline_buttons[0])
        _, team2_ml = extract_button_info(moneyline_buttons[1])
        
        # Return in the standardized structure
        return {
            "team1_name": team1_name,
            "team1_spread": team1_spread,
            "team1_spread_odds": team1_spread_odds,
            "team1_over": over_value,
            "team1_over_odds": over_odds,
            "team1_under": under_value,
            "team1_under_odds": under_odds,
            "team1_moneyline": team1_ml,
            
            "team2_name": team2_name,
            "team2_spread": team2_spread,
            "team2_spread_odds": team2_spread_odds,
            "team2_over": over_value,
            "team2_over_odds": over_odds,
            "team2_under": under_value,
            "team2_under_odds": under_odds,
            "team2_moneyline": team2_ml
        }
        
    except Exception as e:
        return {"error": f"ESPN error for {team_name}: {str(e)}"}
    finally:
        if driver:
            time.sleep(1)
            driver.quit()


# ======================================================================
# ========================= IMAGE OVERLAY CODE =========================
# ======================================================================

def create_odds_table_overlay(
    all_odds_data, 
    image_path="bg.png", 
    output_path="odds_custom.png",
    box_bg_color=(230,200,250,255),   # Slight light purple background
    text_align="left",               
    vertical_offset_fraction=0.55
):
    """
    Creates an odds overlay where each site now has three boxes:
      1) Team 1 lines (no O/U)
      2) Team 2 lines (no O/U)
      3) Over/Under lines (dedicated box)

    The top row is always team1 (spread + ML), 
    the middle row is team2 (spread + ML),
    and the bottom row is the new Over/Under box.
    """

    def approx_text_size(text, font):
        try:
            base_size = font.size
        except AttributeError:
            base_size = 16
        char_width = 0.6 * base_size
        est_width = int(len(text) * char_width)
        est_height = base_size
        return (est_width, est_height)

    # Load base image or fallback
    try:
        base_img = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"Error loading image {image_path}: {e}")
        base_img = Image.new("RGBA", (1200, 800), (30, 30, 30, 255))

    width, height = base_img.size
    draw = ImageDraw.Draw(base_img)

    # Fonts
    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
        cell_font = ImageFont.truetype("arial.ttf", 20)
    except:
        title_font = ImageFont.load_default()
        cell_font = ImageFont.load_default()

    # Title text
    #title_text = "NBA Odds (Custom Layout)"
    title_text = ""

    def draw_centered_title(txt, top_y):
        tw, th = approx_text_size(txt, title_font)
        draw.text(((width - tw) // 2, top_y), txt, font=title_font, fill=(255,255,255))

    draw_centered_title(title_text, top_y=10)

    # Order in which sites will appear (columns left to right)
    ordered_sites = ["HardRock", "BetMGM", "Bet365", "Caesars", "ESPN"]

    # We now have 3 rows: 
    #   Row 0 => team1 (no O/U)
    #   Row 1 => team2 (no O/U)
    #   Row 2 => Over/Under only
    rows = 3
    cols = len(ordered_sites)

    # Prepare data structures: cell_lines[row][col]
    cell_lines = [[None]*cols for _ in range(rows)]

    def build_cell_lines_teamonly(site_name, odds_data, is_team1=True):
        """
        Returns lines for spread + ML only (no Over/Under).
        """
        if "error" in odds_data:
            return [f"{site_name} - No Data"]

        prefix = "team1_" if is_team1 else "team2_"
        this_team_name = odds_data.get(prefix + "name", "?")
        spread         = odds_data.get(prefix + "spread", "N/A")
        spread_odds    = odds_data.get(prefix + "spread_odds", "N/A")
        moneyline      = odds_data.get(prefix + "moneyline", "N/A")

        return [
            f"{site_name} - {this_team_name}",
            f"Spread: {spread} ({spread_odds})",
            f"ML: {moneyline}"
        ]

    def build_cell_lines_totals(site_name, odds_data):
        """
        Returns a dedicated Over/Under box for the game.
        We'll pull from the 'team1_' keys, since 
        Over/Under is typically the same for both teams.
        """
        if "error" in odds_data:
            return [f"{site_name} - Totals", "No O/U Data"]

        over_val   = odds_data.get("team1_over", "N/A")
        over_odds  = odds_data.get("team1_over_odds", "N/A")
        under_val  = odds_data.get("team1_under", "N/A")
        under_odds = odds_data.get("team1_under_odds", "N/A")

        return [
            f"{site_name} - Totals",
            f"Over: {over_val} ({over_odds})",
            f"Under: {under_val} ({under_odds})"
        ]

    # Build the lines for each site
    for col_idx, site_name in enumerate(ordered_sites):
        site_data = all_odds_data.get(site_name, {})

        # Row 0 => Team 1 lines
        cell_lines[0][col_idx] = build_cell_lines_teamonly(site_name, site_data, is_team1=True)

        # Row 1 => Team 2 lines
        cell_lines[1][col_idx] = build_cell_lines_teamonly(site_name, site_data, is_team1=False)

        # Row 2 => Over/Under box
        cell_lines[2][col_idx] = build_cell_lines_totals(site_name, site_data)

    # Measure each cell to handle layout
    cell_sizes = [[(0,0)]*cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            lines = cell_lines[r][c]
            max_line_width = 0
            total_height = 0
            for line in lines:
                lw, lh = approx_text_size(line, cell_font)
                if lw > max_line_width:
                    max_line_width = lw
                total_height += (lh + 2)  # small gap
            raw_width  = max_line_width + 10
            raw_height = total_height + 10
            # Shrink box width by 20% and expand height by 20%
            box_width = int(raw_width * 0.8)
            box_height = int(raw_height * 0.8 * 1.2)
            cell_sizes[r][c] = (box_width, box_height)

    # Determine column widths / row heights
    col_widths  = [max(cell_sizes[r][c][0] for r in range(rows)) for c in range(cols)]
    row_heights = [max(cell_sizes[r][c][1] for c in range(cols)) for r in range(rows)]

    # Spacing
    x_spacing = 15
    y_spacing = 25

    total_grid_width = sum(col_widths) + (cols-1)*x_spacing
    total_grid_height = sum(row_heights) + (rows-1)*y_spacing

    top_left_x = (width - total_grid_width)//2
    top_left_y = int((height - total_grid_height)*vertical_offset_fraction)

    # Draw each cell
    for r in range(rows):
        for c in range(cols):
            w, h = cell_sizes[r][c]
            cell_x = top_left_x + sum(col_widths[:c]) + x_spacing*c
            cell_y = top_left_y + sum(row_heights[:r]) + y_spacing*r

            # Draw the box
            draw.rectangle(
                [(cell_x, cell_y), (cell_x + w, cell_y + h)],
                fill=box_bg_color,
                outline=(0,0,0)
            )

            # Write the text lines
            lines = cell_lines[r][c]
            current_y = cell_y + 5
            for line in lines:
                lw, lh = approx_text_size(line, cell_font)
                if text_align.lower() == "left":
                    line_x = cell_x + 5
                elif text_align.lower() == "right":
                    line_x = cell_x + w - lw - 5
                else:
                    line_x = cell_x + (w - lw)//2

                draw.text((line_x, current_y), line, font=cell_font, fill=(0,0,0))
                current_y += lh + 2

    # Timestamp at the bottom
    #stamp_str = datetime.now().strftime("Generated: %Y-%m-%d %H:%M:%S")
    stamp_str = datetime.now().strftime("")
    draw.text((20, height - 30), stamp_str, font=cell_font, fill=(255,255,255))

    final_img = base_img.convert("RGB")
    final_img.save(output_path, quality=100)
    print(f"Saved custom layout to {output_path}")


# ======================================================================
# =============================== MAIN CODE ============================
# ======================================================================

def main():
    """
    MASTER SCRIPT MAIN:
    1) Prompt user for team name
    2) Call each site's "get_game_odds" function
    3) Gather results into a dictionary
    4) Standardize team1_name/team2_name across all sites to match HardRock's
       naming if available (or else the first non-error site).
    5) Pass to the "create_odds_table_overlay" function to generate an image
    """
    team_name = input("Enter a team name (e.g., Spurs): ").strip()
    
    # Gather data
    all_odds = {}
    
    # HardRock
    hr_data = hardrock_get_game_odds(team_name)
    all_odds["HardRock"] = hr_data
    
    # BetMGM
    mgm_data = betmgm_get_game_odds(team_name)
    all_odds["BetMGM"] = mgm_data
    
    # Bet365
    b365_data = bet365_get_game_odds(team_name)
    all_odds["Bet365"] = b365_data
    
    # Caesars
    czr_data = caesars_get_game_odds(team_name)
    all_odds["Caesars"] = czr_data
    
    # ESPN
    espn_data = espn_get_game_odds(team_name)
    all_odds["ESPN"] = espn_data
    
    # Decide our "canonical" team names from HardRock if no error, else from next available site
    if "error" not in hr_data:
        canonical_team1_name = hr_data["team1_name"]
        canonical_team2_name = hr_data["team2_name"]
    else:
        # fallback: find next site that isn't an error
        canonical_team1_name = "Team1"
        canonical_team2_name = "Team2"
        for site in ["BetMGM", "Bet365", "Caesars", "ESPN"]:
            if site in all_odds and "error" not in all_odds[site]:
                canonical_team1_name = all_odds[site]["team1_name"]
                canonical_team2_name = all_odds[site]["team2_name"]
                break

    # Override team names in all sites
    for site, data in all_odds.items():
        if "error" not in data:
            data["team1_name"] = canonical_team1_name
            data["team2_name"] = canonical_team2_name

    # Print raw results for inspection
    print("\nRAW SCRAPE RESULTS (with unified team names if possible):")
    for site, data in all_odds.items():
        print(f"----- {site} -----")
        if "error" in data:
            print("Error:", data["error"])
        else:
            print(data)
    
    # Create the image with table overlay
    create_odds_table_overlay(
        all_odds,
        image_path=DEFAULT_IMAGE_PATH,
        output_path=OUTPUT_IMAGE_PATH
    )


if __name__ == "__main__":
    main()
