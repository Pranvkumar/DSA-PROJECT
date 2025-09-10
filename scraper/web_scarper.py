# Required installations:
# pip install selenium webdriver-manager fake-useragent beautifulsoup4 requests pandas textblob undetected-chromedriver

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
import undetected_chromedriver as uc
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
    """Advanced Twitter/X scraper using Selenium and requests"""
    
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
        """Setup undetected Chrome driver"""
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.ua.random}')
            # options.add_argument('--headless') # Run headless for production
            
            self.driver = uc.Chrome(options=options)
            logger.info("✅ Chrome driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup Chrome driver: {str(e)}")
            return False
    
    def scrape_nitter_search(self, query: str, max_tweets: int = 50) -> List[dict]:
        """Scrape tweets from Nitter (Twitter mirror) - more reliable"""
        tweets = []
        nitter_instances = [
            "nitter.net",
            "nitter.it",
            "nitter.unixfox.eu",
            "nitter.domain.glass"
        ]
        
        for instance in nitter_instances:
            try:
                search_url = f"https://{instance}/search?f=tweets&q={quote(query)}&since={ (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d') }"
                
                response = self.session.get(search_url, timeout=15)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    tweet_containers = soup.find_all('div', class_='timeline-item')
                    
                    for container in tweet_containers[:max_tweets]:
                        try:
                            tweet_data = self.extract_nitter_tweet_data(container)
                            if tweet_data:
                                tweets.append(tweet_data)
                        except Exception as e:
                            logger.debug(f"Error parsing tweet: {str(e)}")
                            continue
                    
                    if tweets:
                        logger.info(f"✅ Scraped {len(tweets)} tweets from {instance}")
                        return tweets # Return as soon as we get results from one instance
                        
            except Exception as e:
                logger.debug(f"Failed to scrape from {instance}: {str(e)}")
                continue
        
        return tweets
    
    def extract_nitter_tweet_data(self, container) -> Optional[dict]:
        """Extract tweet data from Nitter HTML container"""
        try:
            username = container.find('a', class_='fullname').text.strip()
            handle = container.find('a', class_='username').text.strip().replace('@', '')
            content = container.find('div', class_='tweet-content').get_text(strip=True)
            
            # Use a more robust way to find stats
            stats_div = container.find('div', class_='tweet-stats')
            replies = self.parse_count(stats_div.find('span', class_='icon-comment').parent.text)
            retweets = self.parse_count(stats_div.find('span', class_='icon-retweet').parent.text)
            likes = self.parse_count(stats_div.find('span', class_='icon-heart').parent.text)

            time_elem = container.find('span', class_='tweet-date').find('a')
            timestamp = time_elem['title'] if time_elem else datetime.now().strftime("%Y-%m-%d %H:%M")
            
            tweet_id = f"nitter_{hash(content + username)}"
            verified = bool(container.find('span', class_='verified-icon'))
            
            return {
                'username': username, 'handle': handle, 'content': content,
                'timestamp': timestamp, 'retweets': retweets, 'likes': likes,
                'replies': replies, 'tweet_id': tweet_id, 'verified': verified,
                'source': 'NITTER_SCRAPE'
            }
        except Exception as e:
            logger.debug(f"Error extracting nitter tweet data: {str(e)}")
            return None

    def scrape_twitter_selenium(self, query: str, max_tweets: int = 50) -> List[dict]:
        """Scrape Twitter directly using Selenium"""
        tweets = []
        
        if not self.setup_driver():
            return tweets
            
        try:
            search_url = f"https://twitter.com/search?q={quote(query)}&src=typed_query&f=live"
            self.driver.get(search_url)
            
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweet"]'))
            )
            
            tweet_ids = set()
            scroll_attempts = 0
            
            while len(tweets) < max_tweets and scroll_attempts < 15:
                tweet_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="tweet"]')
                
                for element in tweet_elements:
                    tweet_data = self.extract_selenium_tweet_data(element)
                    if tweet_data and tweet_data['tweet_id'] not in tweet_ids:
                        tweets.append(tweet_data)
                        tweet_ids.add(tweet_data['tweet_id'])
                        if len(tweets) >= max_tweets:
                            break
                
                if len(tweets) >= max_tweets:
                    break

                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                scroll_attempts += 1
                
            logger.info(f"✅ Scraped {len(tweets)} tweets using Selenium")
            
        except Exception as e:
            logger.error(f"❌ Error scraping with Selenium: {str(e)}")
        
        finally:
            if self.driver:
                self.driver.quit()
        
        return tweets

    def extract_selenium_tweet_data(self, element) -> Optional[dict]:
        """Extract tweet data from Selenium WebElement"""
        try:
            user_info = element.find_element(By.CSS_SELECTOR, '[data-testid="User-Name"]')
            username = user_info.find_element(By.CSS_SELECTOR, "span").text
            handle = user_info.find_element(By.CSS_SELECTOR, "a").get_attribute('href').split('/')[-1]
            
            content = element.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]').text
            
            replies = self.parse_count(element.find_element(By.CSS_SELECTOR, '[data-testid="reply"]').text)
            retweets = self.parse_count(element.find_element(By.CSS_SELECTOR, '[data-testid="retweet"]').text)
            likes = self.parse_count(element.find_element(By.CSS_SELECTOR, '[data-testid="like"]').text)

            timestamp = element.find_element(By.TAG_NAME, 'time').get_attribute('datetime')
            tweet_id = f"selenium_{handle}_{timestamp}"
            
            verified = False
            try:
                element.find_element(By.CSS_SELECTOR, '[data-testid="icon-verified"]')
                verified = True
            except NoSuchElementException:
                pass
            
            return {
                'username': username, 'handle': handle, 'content': content,
                'timestamp': timestamp, 'retweets': retweets, 'likes': likes,
                'replies': replies, 'tweet_id': tweet_id, 'verified': verified,
                'source': 'SELENIUM_SCRAPE'
            }
        except Exception as e:
            logger.debug(f"Error extracting Selenium tweet data: {str(e)}")
            return None

    def parse_count(self, count_str: str) -> int:
        """Parse count strings like '1.2K', '5M', etc."""
        count_str = count_str.strip().upper().replace(',', '')
        if not count_str: return 0
        try:
            if 'K' in count_str:
                return int(float(count_str.replace('K', '')) * 1_000)
            elif 'M' in count_str:
                return int(float(count_str.replace('M', '')) * 1_000_000)
            return int(count_str)
        except (ValueError, TypeError):
            return 0
    
    def scrape_multiple_sources(self, query: str, max_tweets: int = 100) -> List[dict]:
        """Scrape from multiple sources for better coverage"""
        logger.info(f"🔍 Searching Nitter instances for: {query}")
        all_tweets = self.scrape_nitter_search(query, max_tweets)
        
        if len(all_tweets) < max_tweets / 2:
            logger.info(f"🔍 Using Selenium for additional tweets, as Nitter returned {len(all_tweets)}.")
            selenium_tweets = self.scrape_twitter_selenium(query, max_tweets - len(all_tweets))
            all_tweets.extend(selenium_tweets)
        
        unique_tweets = []
        seen_content = set()
        for tweet in all_tweets:
            content_hash = hash(tweet['content'])
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_tweets.append(tweet)
        
        logger.info(f"✅ Total unique tweets collected for '{query}': {len(unique_tweets)}")
        return unique_tweets

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
    
    def search_ocean_hazards(self, max_tweets_per_keyword: int = 20) -> List[OceanHazardTweet]:
        """Search for real ocean hazard tweets using web scraping"""
        logger.info("🌊 Starting real Twitter/X data collection...")
        all_tweets = []
        
        priority_keywords = KEYWORDS[:8] # Focus on most important keywords
        
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
        return unique_tweets
    
    def get_fallback_tech_demo_tweets(self) -> List[OceanHazardTweet]:
        """Fallback demo tweets with tech/space theme (non-ocean topics)"""
        logger.info("🔧 Using fallback demo data.")
        demo_data = [
            {"content": "🚀 SpaceX successfully launched 60 more Starlink satellites! Global internet coverage expanding rapidly. The future is here! #SpaceX #Technology", "username": "SpaceFan2024", "handle": "spacefan2024", "keywords": [], "category": "tech"},
            {"content": "AI breakthrough: New machine learning model achieves 99% accuracy in medical diagnosis. Healthcare will never be the same! 🏥💡 #AI #HealthTech", "username": "TechNews", "handle": "technews", "keywords": [], "category": "tech"},
            {"content": "Crypto market is crashing again 📉 Bitcoin down 15% today. HODL or sell? This volatility is insane! #Bitcoin #Crypto", "username": "CryptoTrader", "handle": "cryptotrader", "keywords": [], "category": "finance"},
            {"content": "Just tried the new iPhone 15 Pro Max camera. The photo quality is absolutely incredible! Apple keeps raising the bar 📸✨ #iPhone15 #Photography", "username": "TechReviewer", "handle": "techreviewer", "keywords": [], "category": "tech"},
            {"content": "Electric vehicle sales surged 40% this quarter! Tesla, Ford, and GM leading the charge. Goodbye gas stations! ⚡🚗 #EV #CleanEnergy", "username": "GreenTech", "handle": "greentech", "keywords": [], "category": "eco"}
        ]
        
        tweets = []
        for i, data in enumerate(demo_data):
            sentiment_score, sentiment_label, confidence = self.analyze_sentiment(data["content"])
            tweet = OceanHazardTweet(
                username=data["username"], handle=data["handle"], content=data["content"],
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"), retweets=random.randint(10, 500),
                likes=random.randint(50, 2000), replies=random.randint(5, 200),
                tweet_id=f"fallback_{i+1:03d}", matched_keywords=data["keywords"],
                sentiment_score=sentiment_score, sentiment_label=sentiment_label,
                confidence=confidence, hazard_category=data["category"], source="FALLBACK_DEMO",
                verified=random.choice([True, False])
            )
            tweets.append(tweet)
        return tweets
    
    def analyze_sentiment(self, text: str) -> tuple:
        """Advanced sentiment analysis optimized for disaster/ocean hazard context"""
        text_key = text.lower().strip()
        if text_key in self.sentiment_cache:
            return self.sentiment_cache[text_key]
        
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        
        disaster_negative = ["disaster", "devastation", "destroyed", "catastrophic", "emergency", "crisis", "collapse", "dying", "death", "evacuation"]
        disaster_positive = ["restored", "recovery", "saved", "protection", "resilient", "hope", "success"]
        
        negative_boost = sum(1 for word in disaster_negative if word in text.lower())
        positive_boost = sum(1 for word in disaster_positive if word in text.lower())
        
        polarity += (positive_boost * 0.2) - (negative_boost * 0.3)
        polarity = max(-1.0, min(1.0, polarity)) # Clamp value
        
        label = "positive" if polarity > 0.1 else "negative" if polarity < -0.1 else "neutral"
        confidence = min(abs(polarity) * 1.5, 1.0)
        
        result = (polarity, label, confidence)
        self.sentiment_cache[text_key] = result
        return result
    
    def find_matching_keywords(self, text: str) -> List[str]:
        """Find ocean hazard keywords in tweet text"""
        return [kw for kw in (KEYWORDS + EXTENDED_KEYWORDS) if kw.lower() in text.lower()]
    
    def categorize_hazard(self, keywords: List[str]) -> str:
        """Categorize the type of ocean hazard"""
        for category, cat_keywords in self.hazard_categories.items():
            if any(kw in cat_keywords for kw in keywords):
                return category
        return "general"
    
    def generate_sentiment_report(self, tweets: List[OceanHazardTweet]) -> Dict:
        """Generate comprehensive sentiment analysis report"""
        if not tweets: return {"error": "No tweets to analyze"}
        
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
    
    def save_results(self, tweets: List[OceanHazardTweet], filename_prefix: str = "ocean_hazard"):
        """Save results to JSON and CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        json_filename = f"{filename_prefix}_tweets_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump([asdict(t) for t in tweets], f, indent=2, ensure_ascii=False)
            
        csv_filename = f"{filename_prefix}_analysis_{timestamp}.csv"
        pd.DataFrame([asdict(t) for t in tweets]).to_csv(csv_filename, index=False)
        
        report_filename = f"{filename_prefix}_report_{timestamp}.json"
        report = self.generate_sentiment_report(tweets)
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        logger.info(f"💾 Results saved:")
        logger.info(f"  📄 Tweet data: {json_filename}")
        logger.info(f"  📊 CSV analysis: {csv_filename}")
        logger.info(f"  📈 Sentiment report: {report_filename}")

def display_tweets(tweets: List[OceanHazardTweet], limit: int = 5):
    """Display tweets in a formatted way"""
    print(f"\n{'='*80}\n🌊 TWEET ANALYSIS ({'REAL DATA' if tweets[0].source != 'FALLBACK_DEMO' else 'FALLBACK DEMO'})\n{'='*80}")
    
    for i, tweet in enumerate(tweets[:limit], 1):
        emoji = {"positive": "😊", "negative": "😰", "neutral": "😐"}.get(tweet.sentiment_label, "🤔")
        verified_badge = "✅" if tweet.verified else ""
        
        print(f"\n{i}. {emoji} @{tweet.handle} {verified_badge} ({tweet.sentiment_label.upper()}: {tweet.sentiment_score:.2f})")
        print(f"   📂 Category: {tweet.hazard_category.upper()}")
        print(f"   🏷️ Keywords: {', '.join(tweet.matched_keywords) if tweet.matched_keywords else 'N/A'}")
        print(f"   💬 {tweet.content}")
        print(f"   📊 ❤️ {tweet.likes:,} | 🔄 {tweet.retweets:,} | 💬 {tweet.replies:,}")
        print(f"   🕒 {tweet.timestamp} | 📡 {tweet.source}")
        print("-" * 80)

def main():
    """Main execution function"""
    print("🚀 Starting Ocean Hazard Sentiment Analysis with Web Scraping...")
    print(f"📋 Monitoring {len(KEYWORDS)} primary and {len(EXTENDED_KEYWORDS)} extended keywords.")
    print("⚠️ Note: Web scraping can be slow and may require human verification if captcha appears.")
    
    analyzer = OceanHazardAnalyzer()
    
    # Attempt to get real-time data
    tweets_to_analyze = analyzer.search_ocean_hazards(max_tweets_per_keyword=15)
    
    # Use fallback data if scraping fails or returns no results
    if not tweets_to_analyze:
        print("\n⚠️ Scraping did not return sufficient data. Switching to fallback demo tweets.")
        tweets_to_analyze = analyzer.get_fallback_tech_demo_tweets()
        filename_prefix = "fallback_demo"
    else:
        filename_prefix = "ocean_hazard_real"

    if tweets_to_analyze:
        display_tweets(tweets_to_analyze, limit=10)
        analyzer.save_results(tweets_to_analyze, filename_prefix)
        print("\n✅ Analysis complete. Check the generated JSON and CSV files for full details.")
    else:
        print("\n❌ No tweets found to analyze. Exiting.")

if __name__ == "__main__":
    main()
