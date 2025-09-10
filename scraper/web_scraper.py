# Required installations:
# pip install selenium webdriver-manager fake-useragent beautifulsoup4 requests pandas textblob

import json
import time
import random
import logging
import os
import platform
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import re
from textblob import TextBlob
from collections import Counter
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Try multiple browser options
try:
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
    CHROME_AVAILABLE = True
except ImportError:
    CHROME_AVAILABLE = False

try:
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    EDGE_AVAILABLE = True
except ImportError:
    EDGE_AVAILABLE = False

try:
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from webdriver_manager.firefox import GeckoDriverManager
    FIREFOX_AVAILABLE = True
except ImportError:
    FIREFOX_AVAILABLE = False

from urllib.parse import quote
import csv
from fake_useragent import UserAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# List of ocean hazard keywords to search
KEYWORDS = [
    "ocean hazard", "tsunami", "storm surge", "hurricane", "cyclone", "typhoon",
    "flood", "coastal erosion", "sea level rise", "marine pollution", "oil spill",
    "red tide", "whirlpool", "rip current", "underwater earthquake"
]

EXTENDED_KEYWORDS = [
    "climate change ocean", "rising sea levels", "ocean warming", "coral bleaching",
    "marine heatwave", "coastal flooding", "beach erosion", "storm damage",
    "ocean acidification", "marine ecosystem"
]

@dataclass
class OceanHazardTweet:
    username: str
    handle: str
    content: str
    timestamp: str
    retweets: int
    likes: int
    replies: int
    tweet_id: str
    matched_keywords: List[str]
    sentiment_score: float
    sentiment_label: str
    confidence: float
    hazard_category: str
    source: str
    location: Optional[str] = None
    verified: bool = False

class TwitterScraper:
    """Advanced Twitter/X scraper with multiple browser fallbacks"""
    
    def __init__(self):
        self.driver = None
        self.ua = UserAgent()
        self.session = requests.Session()
        self.setup_session()
        
    def setup_session(self):
        """Setup requests session with proper headers"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def setup_driver(self):
        """Setup driver with multiple fallback options"""
        drivers_to_try = []
        
        # Add available drivers
        if CHROME_AVAILABLE:
            drivers_to_try.append('chrome')
        if FIREFOX_AVAILABLE:
            drivers_to_try.append('firefox')
        if EDGE_AVAILABLE:
            drivers_to_try.append('edge')
            
        logger.info(f"Available drivers to try: {drivers_to_try}")
        
        for driver_name in drivers_to_try:
            try:
                if driver_name == 'chrome':
                    return self.setup_chrome_driver()
                elif driver_name == 'firefox':
                    return self.setup_firefox_driver()
                elif driver_name == 'edge':
                    return self.setup_edge_driver()
            except Exception as e:
                logger.warning(f"Failed to setup {driver_name} driver: {str(e)}")
                continue
                
        # Try manual driver paths as last resort
        logger.info("Trying manual driver detection...")
        return self.setup_manual_driver()
    
    def setup_chrome_driver(self):
        """Setup Chrome driver"""
        try:
            options = ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.ua.random}')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--headless')
            
            # Try webdriver manager first, then fallback
            try:
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                logger.warning(f"WebDriver manager failed for Chrome: {e}")
                # Try system Chrome driver
                self.driver = webdriver.Chrome(options=options)
                
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("✅ Chrome driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup Chrome driver: {str(e)}")
            return False
    
    def setup_firefox_driver(self):
        """Setup Firefox driver"""
        try:
            options = FirefoxOptions()
            options.add_argument('--headless')
            options.add_argument('--width=1920')
            options.add_argument('--height=1080')
            
            try:
                service = FirefoxService(GeckoDriverManager().install())
                self.driver = webdriver.Firefox(service=service, options=options)
            except Exception as e:
                logger.warning(f"WebDriver manager failed for Firefox: {e}")
                self.driver = webdriver.Firefox(options=options)
                
            logger.info("✅ Firefox driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup Firefox driver: {str(e)}")
            return False
    
    def setup_edge_driver(self):
        """Setup Edge driver"""
        try:
            options = EdgeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.ua.random}')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--headless')
            
            try:
                service = EdgeService(EdgeChromiumDriverManager().install())
                self.driver = webdriver.Edge(service=service, options=options)
            except Exception as e:
                logger.warning(f"WebDriver manager failed for Edge: {e}")
                self.driver = webdriver.Edge(options=options)
                
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("✅ Edge driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup Edge driver: {str(e)}")
            return False
            
    def setup_manual_driver(self):
        """Try to use system-installed drivers without webdriver-manager"""
        manual_drivers = [
            ('chrome', webdriver.Chrome),
            ('firefox', webdriver.Firefox), 
            ('edge', webdriver.Edge)
        ]
        
        for driver_name, driver_class in manual_drivers:
            try:
                logger.info(f"Trying manual {driver_name} driver...")
                if driver_name == 'chrome':
                    options = ChromeOptions()
                    options.add_argument('--headless')
                    options.add_argument('--no-sandbox')
                    self.driver = driver_class(options=options)
                elif driver_name == 'firefox':
                    options = FirefoxOptions()
                    options.add_argument('--headless')
                    self.driver = driver_class(options=options)
                elif driver_name == 'edge':
                    options = EdgeOptions()
                    options.add_argument('--headless')
                    self.driver = driver_class(options=options)
                    
                logger.info(f"✅ Manual {driver_name} driver initialized successfully")
                return True
            except Exception as e:
                logger.warning(f"Manual {driver_name} driver failed: {str(e)}")
                continue
                
        return False
    
    def scrape_nitter_search(self, query: str, max_tweets: int = 50) -> List[dict]:
        """Scrape tweets from Nitter instances"""
        tweets = []
        # Updated working Nitter instances
        nitter_instances = [
            "nitter.poast.org",
            "nitter.privacydev.net", 
            "nitter.lunar.icu",
            "nitter.ktachibana.party",
            "nitter.fdn.fr"
        ]
        
        for instance in nitter_instances:
            try:
                search_url = f"https://{instance}/search?f=tweets&q={quote(query)}"
                logger.info(f"Trying Nitter instance: {instance}")
                
                response = self.session.get(search_url, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Look for different possible tweet containers
                    tweet_containers = (
                        soup.find_all('div', class_='timeline-item') or
                        soup.find_all('div', class_='tweet') or
                        soup.find_all('article') or
                        soup.find_all('div', class_='status')
                    )
                    
                    logger.info(f"Found {len(tweet_containers)} potential tweet containers")
                    
                    for container in tweet_containers[:max_tweets]:
                        try:
                            tweet_data = self.extract_nitter_tweet_data(container)
                            if tweet_data and self.is_ocean_hazard_relevant(tweet_data['content']):
                                tweets.append(tweet_data)
                        except Exception as e:
                            logger.debug(f"Error parsing tweet: {str(e)}")
                            continue
                    
                    if tweets:
                        logger.info(f"✅ Scraped {len(tweets)} tweets from {instance}")
                        return tweets
                else:
                    logger.debug(f"HTTP {response.status_code} from {instance}")
                        
            except Exception as e:
                logger.debug(f"Failed to scrape from {instance}: {str(e)}")
                continue
        
        logger.warning("No Nitter instances returned results")
        return tweets
    
    def is_ocean_hazard_relevant(self, text: str) -> bool:
        """Check if tweet content is relevant to ocean hazards"""
        text_lower = text.lower()
        ocean_hazard_terms = KEYWORDS + EXTENDED_KEYWORDS
        return any(term.lower() in text_lower for term in ocean_hazard_terms)
    
    def extract_nitter_tweet_data(self, container) -> Optional[dict]:
        """Extract tweet data from Nitter HTML container with multiple fallbacks"""
        try:
            # Try multiple selectors for username
            username = None
            for selector in ['.fullname', '.tweet-name', '.name', '[data-name]']:
                elem = container.select_one(selector)
                if elem:
                    username = elem.get_text(strip=True)
                    break
            
            # Try multiple selectors for handle
            handle = None
            for selector in ['.username', '.tweet-username', '.handle', 'a[href*="/"]']:
                elem = container.select_one(selector)
                if elem:
                    handle = elem.get_text(strip=True).replace('@', '')
                    break
            
            # Try multiple selectors for content
            content = None
            for selector in ['.tweet-content', '.tweet-text', '.status-content', '.content']:
                elem = container.select_one(selector)
                if elem:
                    content = elem.get_text(strip=True)
                    break
            
            if not all([username, handle, content]):
                return None
            
            # Default stats
            replies = retweets = likes = 0
            
            # Generate unique tweet ID
            tweet_id = f"nitter_{hash(content + username + str(time.time()))}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            return {
                'username': username, 'handle': handle, 'content': content,
                'timestamp': timestamp, 'retweets': retweets, 'likes': likes,
                'replies': replies, 'tweet_id': tweet_id, 'verified': False,
                'source': 'NITTER_SCRAPE'
            }
        except Exception as e:
            logger.debug(f"Error extracting nitter tweet data: {str(e)}")
            return None

    def scrape_twitter_selenium(self, query: str, max_tweets: int = 50) -> List[dict]:
        """Scrape Twitter directly using Selenium with fallback options"""
        tweets = []
        
        if not self.setup_driver():
            logger.error("Failed to initialize any browser driver")
            return tweets
            
        try:
            search_url = f"https://twitter.com/search?q={quote(query)}&src=typed_query&f=live"
            self.driver.get(search_url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Try to find tweets with multiple selectors
            tweet_selectors = [
                '[data-testid="tweet"]',
                'article[data-testid="tweet"]',
                '.css-1dbjc4n[data-testid="tweet"]',
                'div[data-testid="tweet"]'
            ]
            
            tweets_found = False
            for selector in tweet_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    tweets_found = True
                    break
                except TimeoutException:
                    continue
            
            if not tweets_found:
                logger.warning("No tweets found with any selector")
                return tweets
            
            tweet_ids = set()
            scroll_attempts = 0
            
            while len(tweets) < max_tweets and scroll_attempts < 10:
                for selector in tweet_selectors:
                    tweet_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in tweet_elements:
                        try:
                            tweet_data = self.extract_selenium_tweet_data(element)
                            if (tweet_data and 
                                tweet_data['tweet_id'] not in tweet_ids and 
                                self.is_ocean_hazard_relevant(tweet_data['content'])):
                                tweets.append(tweet_data)
                                tweet_ids.add(tweet_data['tweet_id'])
                                if len(tweets) >= max_tweets:
                                    break
                        except Exception as e:
                            logger.debug(f"Error processing tweet element: {e}")
                            continue
                    
                    if len(tweets) >= max_tweets:
                        break
                
                if len(tweets) >= max_tweets:
                    break

                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                scroll_attempts += 1
                
            logger.info(f"✅ Scraped {len(tweets)} relevant tweets using Selenium")
            
        except Exception as e:
            logger.error(f"❌ Error scraping with Selenium: {str(e)}")
        
        finally:
            if self.driver:
                self.driver.quit()
        
        return tweets

    def extract_selenium_tweet_data(self, element) -> Optional[dict]:
        """Extract tweet data from Selenium WebElement with multiple fallbacks"""
        try:
            # Try multiple ways to get username and handle
            username = handle = "unknown"
            
            # Try different selectors for user info
            user_selectors = [
                '[data-testid="User-Name"]',
                '.css-1dbjc4n[data-testid="User-Name"]',
                'div[data-testid="User-Name"]'
            ]
            
            for selector in user_selectors:
                try:
                    user_info = element.find_element(By.CSS_SELECTOR, selector)
                    spans = user_info.find_elements(By.TAG_NAME, "span")
                    if spans:
                        username = spans[0].text
                    
                    links = user_info.find_elements(By.TAG_NAME, "a")
                    if links:
                        href = links[0].get_attribute('href')
                        if href and '/' in href:
                            handle = href.split('/')[-1]
                    break
                except:
                    continue
            
            # Try to get tweet text
            content = ""
            text_selectors = [
                '[data-testid="tweetText"]',
                '.css-901oao[data-testid="tweetText"]',
                'div[data-testid="tweetText"]',
                '.tweet-text'
            ]
            
            for selector in text_selectors:
                try:
                    content_elem = element.find_element(By.CSS_SELECTOR, selector)
                    content = content_elem.text
                    break
                except:
                    continue
            
            if not content:
                return None
            
            # Default stats
            replies = retweets = likes = 0
            timestamp = datetime.now().isoformat()
            tweet_id = f"selenium_{handle}_{hash(content)}"
            
            return {
                'username': username, 'handle': handle, 'content': content,
                'timestamp': timestamp, 'retweets': retweets, 'likes': likes,
                'replies': replies, 'tweet_id': tweet_id, 'verified': False,
                'source': 'SELENIUM_SCRAPE'
            }
        except Exception as e:
            logger.debug(f"Error extracting Selenium tweet data: {str(e)}")
            return None

    def parse_count(self, count_str: str) -> int:
        """Parse count strings like '1.2K', '5M', etc."""
        if not count_str:
            return 0
        count_str = count_str.strip().upper().replace(',', '')
        try:
            if 'K' in count_str:
                return int(float(count_str.replace('K', '')) * 1_000)
            elif 'M' in count_str:
                return int(float(count_str.replace('M', '')) * 1_000_000)
            return int(''.join(filter(str.isdigit, count_str)) or '0')
        except (ValueError, TypeError):
            return 0
    
    def scrape_multiple_sources(self, query: str, max_tweets: int = 100) -> List[dict]:
        """Scrape from multiple sources for better coverage"""
        logger.info(f"🔍 Searching for ocean hazard tweets: '{query}'")
        
        # First try Nitter (usually more reliable)
        all_tweets = self.scrape_nitter_search(query, max_tweets)
        
        # If no results from Nitter, try Selenium
        if len(all_tweets) < max_tweets // 2:
            logger.info(f"🔍 Using Selenium for additional tweets (Nitter returned {len(all_tweets)})")
            selenium_tweets = self.scrape_twitter_selenium(query, max_tweets - len(all_tweets))
            all_tweets.extend(selenium_tweets)
        
        # Remove duplicates based on content
        unique_tweets = []
        seen_content = set()
        for tweet in all_tweets:
            content_hash = hash(tweet['content'])
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_tweets.append(tweet)
        
        logger.info(f"✅ Total unique ocean hazard tweets for '{query}': {len(unique_tweets)}")
        return unique_tweets

class MockDataGenerator:
    """Generate mock ocean hazard tweets for testing when scraping fails"""
    
    @staticmethod
    def generate_mock_tweets(num_tweets: int = 20) -> List[dict]:
        """Generate realistic mock ocean hazard tweets"""
        mock_tweets = [
            {
                'username': 'OceanWatch', 'handle': 'oceanwatch', 
                'content': 'Massive tsunami warning issued for Pacific coast. Waves up to 15 feet expected. Evacuate immediately! #tsunami #safety',
                'timestamp': '2024-09-10 14:30', 'retweets': 1200, 'likes': 2500, 'replies': 300,
                'tweet_id': 'mock_1', 'verified': True, 'source': 'MOCK_DATA'
            },
            {
                'username': 'WeatherAlert', 'handle': 'weatheralert',
                'content': 'Hurricane forming in the Atlantic. Storm surge could reach 20 feet along the coast. Prepare now! #hurricane #stormsurge',
                'timestamp': '2024-09-10 12:15', 'retweets': 800, 'likes': 1500, 'replies': 200,
                'tweet_id': 'mock_2', 'verified': True, 'source': 'MOCK_DATA'
            },
            {
                'username': 'ClimateScientist', 'handle': 'climatescience',
                'content': 'Rising sea levels are accelerating coastal erosion worldwide. We need immediate action on climate change.',
                'timestamp': '2024-09-10 10:00', 'retweets': 600, 'likes': 1200, 'replies': 150,
                'tweet_id': 'mock_3', 'verified': False, 'source': 'MOCK_DATA'
            },
            {
                'username': 'MarineBiology', 'handle': 'marinebio',
                'content': 'Coral bleaching event spreading across the Pacific. Ocean warming is devastating marine ecosystems.',
                'timestamp': '2024-09-10 08:45', 'retweets': 400, 'likes': 900, 'replies': 100,
                'tweet_id': 'mock_4', 'verified': False, 'source': 'MOCK_DATA'
            },
            {
                'username': 'EmergencyMgmt', 'handle': 'emergency_mgmt',
                'content': 'Oil spill reported 50 miles offshore. Marine pollution cleanup crews deployed. Wildlife evacuation underway.',
                'timestamp': '2024-09-10 06:30', 'retweets': 750, 'likes': 1100, 'replies': 180,
                'tweet_id': 'mock_5', 'verified': True, 'source': 'MOCK_DATA'
            }
        ]
        
        # Add more mock tweets if needed
        while len(mock_tweets) < num_tweets:
            base_tweet = random.choice(mock_tweets[:5])
            new_tweet = base_tweet.copy()
            new_tweet['tweet_id'] = f"mock_{len(mock_tweets) + 1}"
            new_tweet['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            mock_tweets.append(new_tweet)
        
        return mock_tweets[:num_tweets]

class OceanHazardAnalyzer:
    def __init__(self):
        self.sentiment_cache = {}
        self.scraper = TwitterScraper()
        
        self.hazard_categories = {
            "tsunami": ["tsunami", "underwater earthquake"],
            "storms": ["hurricane", "cyclone", "typhoon", "storm surge", "storm damage"],
            "flooding": ["flood", "coastal flooding", "rising sea levels"],
            "erosion": ["coastal erosion", "beach erosion", "sea level rise"],
            "pollution": ["marine pollution", "oil spill", "red tide", "ocean acidification"],
            "currents": ["rip current", "whirlpool"],
            "climate": ["climate change ocean", "ocean warming", "coral bleaching", "marine heatwave"],
            "general": ["ocean hazard", "marine ecosystem"]
        }
    
    def search_ocean_hazards(self, max_tweets_per_keyword: int = 20, use_mock_data: bool = False) -> List[OceanHazardTweet]:
        """Search for ocean hazard tweets using web scraping or mock data"""
        logger.info("🌊 Starting ocean hazard tweet collection...")
        
        if use_mock_data:
            logger.info("📝 Using mock data for testing...")
            raw_tweets = MockDataGenerator.generate_mock_tweets(50)
            all_tweets = []
            
            for raw_tweet in raw_tweets:
                matched_keywords = self.find_matching_keywords(raw_tweet['content'])
                if matched_keywords:
                    sentiment_score, sentiment_label, confidence = self.analyze_sentiment(raw_tweet['content'])
                    hazard_category = self.categorize_hazard(matched_keywords)
                    
                    tweet = OceanHazardTweet(
                        username=raw_tweet['username'], handle=raw_tweet['handle'],
                        content=raw_tweet['content'], timestamp=raw_tweet['timestamp'],
                        retweets=raw_tweet['retweets'], likes=raw_tweet['likes'],
                        replies=raw_tweet['replies'], tweet_id=raw_tweet['tweet_id'],
                        matched_keywords=matched_keywords, sentiment_score=sentiment_score,
                        sentiment_label=sentiment_label, confidence=confidence,
                        hazard_category=hazard_category, source=raw_tweet['source'],
                        verified=raw_tweet.get('verified', False)
                    )
                    all_tweets.append(tweet)
            
            logger.info(f"✅ Generated {len(all_tweets)} mock ocean hazard tweets")
            return all_tweets
        
        # Real scraping logic
        all_tweets = []
        priority_keywords = KEYWORDS[:5]  # Focus on most important keywords
        
        for keyword in priority_keywords:
            logger.info(f"🔍 Searching for keyword: '{keyword}'")
            try:
                raw_tweets = self.scraper.scrape_multiple_sources(keyword, max_tweets_per_keyword)
                
                for raw_tweet in raw_tweets:
                    matched_keywords = self.find_matching_keywords(raw_tweet['content'])
                    if matched_keywords:
                        sentiment_score, sentiment_label, confidence = self.analyze_sentiment(raw_tweet['content'])
                        hazard_category = self.categorize_hazard(matched_keywords)
                        
                        tweet = OceanHazardTweet(
                            username=raw_tweet['username'], handle=raw_tweet['handle'],
                            content=raw_tweet['content'], timestamp=raw_tweet['timestamp'],
                            retweets=raw_tweet['retweets'], likes=raw_tweet['likes'],
                            replies=raw_tweet['replies'], tweet_id=raw_tweet['tweet_id'],
                            matched_keywords=matched_keywords, sentiment_score=sentiment_score,
                            sentiment_label=sentiment_label, confidence=confidence,
                            hazard_category=hazard_category, source=raw_tweet['source'],
                            verified=raw_tweet.get('verified', False)
                        )
                        all_tweets.append(tweet)
                        
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                logger.error(f"❌ Error searching for '{keyword}': {str(e)}")
                continue
        
        unique_tweets = list({hash(t.content): t for t in all_tweets}.values())
        logger.info(f"✅ Found {len(unique_tweets)} unique ocean hazard tweets")
        
        # If no real tweets found, offer to use mock data
        if not unique_tweets:
            logger.warning("⚠ No ocean hazard tweets found from scraping.")
            user_input = input("Would you like to use mock data for testing? (y/n): ").lower().strip()
            if user_input in ['y', 'yes']:
                return self.search_ocean_hazards(max_tweets_per_keyword, use_mock_data=True)
        
        return unique_tweets
    
    def analyze_sentiment(self, text: str) -> tuple:
        """Advanced sentiment analysis optimized for disaster/ocean hazard context"""
        text_key = text.lower().strip()
        if text_key in self.sentiment_cache:
            return self.sentiment_cache[text_key]
        
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        
        # Ocean/disaster-specific sentiment modifiers
        disaster_negative = ["disaster", "devastation", "destroyed", "catastrophic", "emergency", 
                           "crisis", "collapse", "dying", "death", "evacuation", "warning", 
                           "danger", "threat", "damage", "destroyed", "flooding", "severe"]
        
        disaster_positive = ["restored", "recovery", "saved", "protection", "resilient", 
                           "hope", "success", "safe", "rescue", "prepared", "prevention"]
        
        negative_boost = sum(1 for word in disaster_negative if word in text.lower())
        positive_boost = sum(1 for word in disaster_positive if word in text.lower())
        
        polarity += (positive_boost * 0.2) - (negative_boost * 0.3)
        polarity = max(-1.0, min(1.0, polarity))  # Clamp value
        
        label = "positive" if polarity > 0.1 else "negative" if polarity < -0.1 else "neutral"
        confidence = min(abs(polarity) * 1.5, 1.0)
        
        result = (polarity, label, confidence)
        self.sentiment_cache[text_key] = result
        return result
    
    def find_matching_keywords(self, text: str) -> List[str]:
        """Find ocean hazard keywords in tweet text"""
        text_lower = text.lower()
        return [kw for kw in (KEYWORDS + EXTENDED_KEYWORDS) if kw.lower() in text_lower]
    
    def categorize_hazard(self, keywords: List[str]) -> str:
        """Categorize the type of ocean hazard"""
        for category, cat_keywords in self.hazard_categories.items():
            if any(kw in cat_keywords for kw in keywords):
                return category
        return "general"
    
    def generate_sentiment_report(self, tweets: List[OceanHazardTweet]) -> Dict:
        """Generate comprehensive sentiment analysis report"""
        if not tweets: 
            return {"error": "No tweets to analyze", "total_tweets": 0}
        
        sentiment_counts = Counter(t.sentiment_label for t in tweets)
        
        categories = {}
        for category in set(t.hazard_category for t in tweets):
            cat_tweets = [t for t in tweets if t.hazard_category == category]
            if not cat_tweets: continue
            categories[category] = {
                "total_tweets": len(cat_tweets),
                "sentiment_distribution": dict(Counter(t.sentiment_label for t in cat_tweets)),
                "avg_sentiment_score": round(sum(t.sentiment_score for t in cat_tweets) / len(cat_tweets), 3),
                "avg_engagement": {
                    "likes": round(sum(t.likes for t in cat_tweets) / len(cat_tweets), 1),
                    "retweets": round(sum(t.retweets for t in cat_tweets) / len(cat_tweets), 1)
                }
            }
        
        all_keywords = [kw for t in tweets for kw in t.matched_keywords]
        
        most_negative = min(tweets, key=lambda t: t.sentiment_score)
        most_positive = max(tweets, key=lambda t: t.sentiment_score)
        most_engaging = max(tweets, key=lambda t: t.likes + t.retweets)
        
        return {
            "summary": {
                "total_tweets": len(tweets),
                "sentiment_distribution": dict(sentiment_counts),
                "avg_sentiment_score": round(sum(t.sentiment_score for t in tweets) / len(tweets), 3),
            },
            "by_hazard_category": categories,
            "top_keywords": dict(Counter(all_keywords).most_common(15)),
            "notable_tweets": {
                "most_negative": asdict(most_negative),
                "most_positive": asdict(most_positive),
                "most_engaging": asdict(most_engaging)
            }
        }
    
    def save_results(self, tweets: List[OceanHazardTweet], filename_prefix: str = "ocean_hazard_"):
        """Save results to JSON and CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save tweet data as JSON
        json_filename = f"{filename_prefix}tweets_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump([asdict(t) for t in tweets], f, indent=2, ensure_ascii=False)
            
        # Save as CSV for easy analysis
        csv_filename = f"{filename_prefix}analysis_{timestamp}.csv"
        pd.DataFrame([asdict(t) for t in tweets]).to_csv(csv_filename, index=False)
        
        # Save sentiment report
        report_filename = f"{filename_prefix}report_{timestamp}.json"
        report = self.generate_sentiment_report(tweets)
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        logger.info(f"💾 Results saved:")
        logger.info(f"  📄 Tweet data: {json_filename}")
        logger.info(f"  📊 CSV analysis: {csv_filename}")
        logger.info(f"  📈 Sentiment report: {report_filename}")

def display_tweets(tweets: List[OceanHazardTweet], limit: int = 10):
    """Display tweets in a formatted way"""
    print(f"\n{'='*80}\n🌊 OCEAN HAZARD TWEET ANALYSIS\n{'='*80}")
    
    if not tweets:
        print("❌ No tweets found to display.")
        return
    
    for i, tweet in enumerate(tweets[:limit], 1):
        emoji = {"positive": "😊", "negative": "😰", "neutral": "😐"}.get(tweet.sentiment_label, "🤔")
        verified_badge = "✅" if tweet.verified else ""
        
        print(f"\n{i}. {emoji} @{tweet.handle} {verified_badge} ({tweet.sentiment_label.upper()}: {tweet.sentiment_score:.2f})")
        print(f"   📂 Category: {tweet.hazard_category.upper()}")
        print(f"   🏷 Keywords: {', '.join(tweet.matched_keywords)}")
        print(f"   💬 {tweet.content}")
        print(f"   📊 ❤ {tweet.likes:,} | 🔄 {tweet.retweets:,} | 💬 {tweet.replies:,}")
        print(f"   🕒 {tweet.timestamp} | 📡 {tweet.source}")
        print("-" * 80)

def main():
    """Main execution function with fallback options"""
    print("🚀 Starting Ocean Hazard Sentiment Analysis")
    print(f"📋 Monitoring {len(KEYWORDS)} primary and {len(EXTENDED_KEYWORDS)} extended keywords")
    
    # Check available browsers
    available_browsers = []
    if CHROME_AVAILABLE: available_browsers.append("Chrome")
    if FIREFOX_AVAILABLE: available_browsers.append("Firefox") 
    if EDGE_AVAILABLE: available_browsers.append("Edge")
    
    print(f"🌐 Available browsers: {', '.join(available_browsers) if available_browsers else 'None detected'}")
    
    analyzer = OceanHazardAnalyzer()
    
    # Ask user preference for data source
    print("\n📊 Data Source Options:")
    print("1. Real scraping (may fail due to anti-bot measures)")
    print("2. Mock data (guaranteed to work for testing)")
    
    choice = input("Choose option (1 or 2): ").strip()
    use_mock = choice == "2"
    
    if use_mock:
        print("📝 Using mock data for demonstration...")
    else:
        print("🔍 Attempting real data scraping...")
        print("⚠ Note: This may fail due to:")
        print("   - Driver download issues")
        print("   - Twitter's anti-scraping measures")
        print("   - Network connectivity issues")
    
    # Get ocean hazard data
    tweets_to_analyze = analyzer.search_ocean_hazards(
        max_tweets_per_keyword=15, 
        use_mock_data=use_mock
    )
    
    if tweets_to_analyze:
        print(f"\n✅ Successfully collected {len(tweets_to_analyze)} ocean hazard tweets")
        display_tweets(tweets_to_analyze, limit=10)
        analyzer.save_results(tweets_to_analyze, "ocean_hazard_data_")
        
        # Generate summary statistics
        report = analyzer.generate_sentiment_report(tweets_to_analyze)
        print(f"\n📊 SUMMARY STATISTICS:")
        print(f"   Total tweets analyzed: {report['summary']['total_tweets']}")
        print(f"   Sentiment distribution: {report['summary']['sentiment_distribution']}")
        print(f"   Average sentiment: {report['summary']['avg_sentiment_score']}")
        if 'by_hazard_category' in report:
            print(f"   Top categories: {list(report['by_hazard_category'].keys())[:5]}")
        
        print("\n✅ Analysis complete! Check the generated files for detailed results.")
    else:
        print("\n❌ No ocean hazard tweets found.")
        print("💡 Try running with mock data option (2) to test the analysis functionality.")

if __name__ == "__main__":
    main()
