import json
import time
import random
import logging
from dataclasses import dataclass
from typing import List, Dict
import re
from textblob import TextBlob
from collections import Counter
import pandas as pd
from datetime import datetime
import concurrent.futures

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

class OceanHazardAnalyzer:
    def __init__(self):
        self.sentiment_cache = {}
        
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
    
    def get_demo_tweets(self) -> List[OceanHazardTweet]:
        """Generate comprehensive demo tweets covering all ocean hazard categories"""
        demo_data = [
            # Tsunami Category
            {
                "content": "🚨 URGENT: 7.8 magnitude underwater earthquake triggers tsunami warning for Pacific coast. Evacuations underway, please stay safe everyone! #Tsunami #Emergency",
                "username": "EmergencyAlert", "handle": "emergencyalert", 
                "keywords": ["tsunami", "underwater earthquake"], "category": "tsunami"
            },
            {
                "content": "Devastating tsunami aftermath: entire coastal villages wiped out. The destruction is beyond words. My heart goes out to all victims and their families. 💔",
                "username": "NewsReporter", "handle": "newsreporter", 
                "keywords": ["tsunami"], "category": "tsunami"
            },
            {
                "content": "Amazing how tsunami early warning systems saved thousands of lives today. Technology and preparedness make all the difference! 🙏",
                "username": "DisasterExpert", "handle": "disasterexpert", 
                "keywords": ["tsunami"], "category": "tsunami"
            },
            
            # Storms Category
            {
                "content": "Hurricane Category 5 approaching Florida coast with 180mph winds! This is going to be catastrophic. Storm surge could reach 20 feet. Evacuate NOW! 🌪️",
                "username": "WeatherService", "handle": "weatherservice", 
                "keywords": ["hurricane", "storm surge"], "category": "storms"
            },
            {
                "content": "Typhoon Mawar absolutely destroyed our island. No power, no water, homes flattened. This is the worst natural disaster we've ever experienced. #Typhoon",
                "username": "IslandResident", "handle": "islandresident", 
                "keywords": ["typhoon"], "category": "storms"
            },
            {
                "content": "Incredible footage of cyclone from space! Nature's power is both terrifying and beautiful. Stay safe everyone in the affected areas! 🌀",
                "username": "AstronautMike", "handle": "astronautmike", 
                "keywords": ["cyclone"], "category": "storms"
            },
            {
                "content": "Storm damage cleanup begins after hurricane passed. Community coming together to help rebuild. Amazing to see human resilience! 💪",
                "username": "CommunityHelper", "handle": "communityhelper", 
                "keywords": ["storm damage", "hurricane"], "category": "storms"
            },
            
            # Flooding Category  
            {
                "content": "Coastal flooding getting worse every year due to rising sea levels. My neighborhood floods now with every high tide. Climate change is real! 🌊",
                "username": "CoastalResident", "handle": "coastalresident", 
                "keywords": ["coastal flooding", "rising sea levels"], "category": "flooding"
            },
            {
                "content": "Flash flood emergency! Water rising rapidly in coastal areas. If you're in evacuation zone GET OUT NOW! This is life threatening! ⚠️",
                "username": "FloodWatch", "handle": "floodwatch", 
                "keywords": ["flood"], "category": "flooding"
            },
            {
                "content": "New flood barriers working perfectly! Engineering solutions can protect communities from sea level rise. Great investment for the future! 🔧",
                "username": "CivilEngineer", "handle": "civilengineer", 
                "keywords": ["flood", "sea level rise"], "category": "flooding"
            },
            
            # Erosion Category
            {
                "content": "Our beach is disappearing! Coastal erosion has eaten away 50 feet of shoreline in just 5 years. Soon our house will be underwater 😢",
                "username": "BeachOwner", "handle": "beachowner", 
                "keywords": ["coastal erosion", "beach erosion"], "category": "erosion"
            },
            {
                "content": "Sea level rise is accelerating. Scientists predict 3 feet rise by 2100. Coastal cities need to start planning NOW for managed retreat.",
                "username": "ClimateScientist", "handle": "climatescientist", 
                "keywords": ["sea level rise"], "category": "erosion"
            },
            {
                "content": "Beach nourishment project restored 2 miles of coastline! Sand dunes are growing back and protecting homes from erosion. Nature-based solutions work! 🏖️",
                "username": "CoastalManager", "handle": "coastalmanager", 
                "keywords": ["beach erosion", "coastal erosion"], "category": "erosion"
            },
            
            # Pollution Category
            {
                "content": "MASSIVE oil spill in Gulf of Mexico! Thousands of barrels leaked, marine life dying. This environmental disaster will take decades to recover from 😡",
                "username": "EcoActivist", "handle": "ecoactivist", 
                "keywords": ["oil spill", "marine pollution"], "category": "pollution"
            },
            {
                "content": "Red tide bloom killing fish and sea turtles along the coast. The smell is unbearable. When will we stop polluting our oceans?? 🐢💔",
                "username": "MarineBiologist", "handle": "marinebiologist", 
                "keywords": ["red tide", "marine pollution"], "category": "pollution"
            },
            {
                "content": "Ocean acidification is making shells dissolve. Our lab results are shocking - pH levels dropping faster than ever recorded. Marine life in crisis! 🦪",
                "username": "OceanChemist", "handle": "oceanchemist", 
                "keywords": ["ocean acidification"], "category": "pollution"
            },
            {
                "content": "Beach cleanup collected 50 tons of plastic waste today! Amazing volunteers making a difference. Every piece of trash removed helps marine life! 🐋♻️",
                "username": "CleanOcean", "handle": "cleanocean", 
                "keywords": ["marine pollution"], "category": "pollution"
            },
            
            # Currents Category
            {
                "content": "WARNING: Dangerous rip currents at all beaches today! 3 people already rescued. If caught in rip current, swim parallel to shore then back to beach! 🏊‍♂️",
                "username": "LifeguardService", "handle": "lifeguardservice", 
                "keywords": ["rip current"], "category": "currents"
            },
            {
                "content": "Whirlpool near the lighthouse swallowed a small boat! All passengers rescued safely. Nature's power is incredible and terrifying. Stay away from that area! 🌊",
                "username": "CoastGuard", "handle": "coastguard", 
                "keywords": ["whirlpool"], "category": "currents"
            },
            
            # Climate Category
            {
                "content": "Ocean warming is killing coral reefs worldwide. Water temperatures 5°F above normal causing mass coral bleaching. We're losing paradise forever 🐠💔",
                "username": "CoralScientist", "handle": "coralscientist", 
                "keywords": ["ocean warming", "coral bleaching"], "category": "climate"
            },
            {
                "content": "Marine heatwave in Pacific Ocean breaking all records! Fish populations crashing, entire ecosystems collapsing. Climate change is accelerating! 🌡️",
                "username": "FisheriesExpert", "handle": "fisheriesexpert", 
                "keywords": ["marine heatwave", "climate change ocean"], "category": "climate"
            },
            {
                "content": "Incredible news! Coral restoration project shows 90% survival rate. Resilient corals adapting to warmer water. Hope for our reefs! 🪸✨",
                "username": "ReefRestoration", "handle": "reefrestoration", 
                "keywords": ["coral bleaching", "ocean warming"], "category": "climate"
            },
            
            # General Category
            {
                "content": "Ocean hazards increasing due to climate change. Coastal communities need better early warning systems and adaptation strategies. Science saves lives! 🔬",
                "username": "NOAA_Official", "handle": "noaa_official", 
                "keywords": ["ocean hazard"], "category": "general"
            },
            {
                "content": "Marine ecosystem collapse happening faster than predicted. Jellyfish taking over where fish used to thrive. The ocean food web is breaking down 😰",
                "username": "EcosystemExpert", "handle": "ecosystemexpert", 
                "keywords": ["marine ecosystem"], "category": "general"
            },
            {
                "content": "New research shows marine ecosystems are incredibly resilient when given a chance! Marine protected areas showing amazing recovery. Conservation works! 🐙",
                "username": "MarineConservation", "handle": "marineconservation", 
                "keywords": ["marine ecosystem"], "category": "general"
            }
        ]
        
        tweets = []
        for i, data in enumerate(demo_data):
            sentiment_score, sentiment_label, confidence = self.analyze_sentiment(data["content"])
            
            # Add realistic engagement numbers based on content type and sentiment
            base_engagement = random.randint(50, 300)
            if sentiment_label == "negative" and any(word in data["content"].lower() for word in ["emergency", "urgent", "disaster", "warning"]):
                engagement_multiplier = 3  # Disaster news spreads fast
            elif sentiment_label == "positive":
                engagement_multiplier = 1.5  # Good news gets moderate engagement
            else:
                engagement_multiplier = 1
            
            tweet = OceanHazardTweet(
                username=data["username"],
                handle=data["handle"],
                content=data["content"],
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
                retweets=int(base_engagement * engagement_multiplier * random.uniform(0.3, 0.8)),
                likes=int(base_engagement * engagement_multiplier * random.uniform(1.0, 2.5)),
                replies=int(base_engagement * engagement_multiplier * random.uniform(0.1, 0.4)),
                tweet_id=f"demo_{i+1:03d}",
                matched_keywords=data["keywords"],
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                confidence=confidence,
                hazard_category=data["category"],
                source="DEMO_DATA"
            )
            tweets.append(tweet)
        
        logger.info(f"Generated {len(tweets)} comprehensive demo tweets covering all ocean hazard categories")
        return tweets
    
    def analyze_sentiment(self, text: str) -> tuple:
        """Advanced sentiment analysis optimized for disaster/ocean hazard context"""
        text_key = text.lower().strip()
        if text_key in self.sentiment_cache:
            return self.sentiment_cache[text_key]
        
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            
            # Ocean hazard context adjustments
            disaster_negative = ["disaster", "devastation", "destroyed", "catastrophic", "emergency", "urgent", "crisis", "collapse", "dying", "death", "evacuation"]
            disaster_positive = ["restored", "recovery", "saved", "protection", "resilient", "amazing", "incredible", "hope", "success", "working"]
            
            negative_boost = sum(1 for word in disaster_negative if word in text.lower())
            positive_boost = sum(1 for word in disaster_positive if word in text.lower())
            
            # Adjust polarity based on context
            polarity += (positive_boost * 0.2) - (negative_boost * 0.3)
            polarity = max(-1.0, min(1.0, polarity))  # Keep within bounds
            
            # Determine label
            if polarity > 0.15:
                label = "positive"
            elif polarity < -0.15:
                label = "negative"
            else:
                label = "neutral"
            
            confidence = min(abs(polarity) + 0.2, 1.0)
            
            self.sentiment_cache[text_key] = (polarity, label, confidence)
            return polarity, label, confidence
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {str(e)}")
            return -0.2, "negative", 0.6
    
    def find_matching_keywords(self, text: str) -> List[str]:
        """Find ocean hazard keywords in tweet text"""
        text_lower = text.lower()
        matching_keywords = []
        
        all_keywords = KEYWORDS + EXTENDED_KEYWORDS
        for keyword in all_keywords:
            if keyword.lower() in text_lower:
                matching_keywords.append(keyword)
        
        return matching_keywords
    
    def categorize_hazard(self, keywords: List[str]) -> str:
        """Categorize the type of ocean hazard"""
        keyword_lower = [k.lower() for k in keywords]
        
        category_priority = ["tsunami", "storms", "flooding", "pollution", "erosion", "currents", "climate", "general"]
        
        for category in category_priority:
            category_keywords = self.hazard_categories[category]
            for cat_keyword in category_keywords:
                if any(cat_keyword.lower() in kw for kw in keyword_lower):
                    return category
        
        return "general" if keywords else "unknown"
    
    def search_ocean_hazards(self) -> List[OceanHazardTweet]:
        """Main search function - returns demo tweets"""
        logger.info("Searching for ocean hazard tweets...")
        time.sleep(1)  # Simulate search time
        return self.get_demo_tweets()
    
    def generate_sentiment_report(self, tweets: List[OceanHazardTweet]) -> Dict:
        """Generate comprehensive sentiment analysis report"""
        if not tweets:
            return {"error": "No tweets to analyze"}
        
        # Overall sentiment distribution
        sentiment_counts = Counter(t.sentiment_label for t in tweets)
        
        # Category analysis
        categories = {}
        for category in set(t.hazard_category for t in tweets):
            cat_tweets = [t for t in tweets if t.hazard_category == category]
            categories[category] = {
                "total_tweets": len(cat_tweets),
                "sentiment_distribution": dict(Counter(t.sentiment_label for t in cat_tweets)),
                "avg_sentiment_score": round(sum(t.sentiment_score for t in cat_tweets) / len(cat_tweets), 3),
                "avg_engagement": {
                    "likes": round(sum(t.likes for t in cat_tweets) / len(cat_tweets), 1),
                    "retweets": round(sum(t.retweets for t in cat_tweets) / len(cat_tweets), 1),
                    "replies": round(sum(t.replies for t in cat_tweets) / len(cat_tweets), 1)
                }
            }
        
        # Top keywords
        all_keywords = []
        for tweet in tweets:
            all_keywords.extend(tweet.matched_keywords)
        keyword_counts = Counter(all_keywords)
        
        # Most extreme tweets
        most_negative = min(tweets, key=lambda t: t.sentiment_score)
        most_positive = max(tweets, key=lambda t: t.sentiment_score)
        most_engaging = max(tweets, key=lambda t: t.likes + t.retweets)
        
        return {
            "summary": {
                "total_tweets": len(tweets),
                "sentiment_distribution": dict(sentiment_counts),
                "avg_sentiment_score": round(sum(t.sentiment_score for t in tweets) / len(tweets), 3),
                "total_engagement": {
                    "likes": sum(t.likes for t in tweets),
                    "retweets": sum(t.retweets for t in tweets),
                    "replies": sum(t.replies for t in tweets)
                }
            },
            "by_hazard_category": categories,
            "top_keywords": dict(keyword_counts.most_common(15)),
            "notable_tweets": {
                "most_negative": {
                    "content": most_negative.content,
                    "score": most_negative.sentiment_score,
                    "category": most_negative.hazard_category,
                    "handle": most_negative.handle
                },
                "most_positive": {
                    "content": most_positive.content,
                    "score": most_positive.sentiment_score,
                    "category": most_positive.hazard_category,
                    "handle": most_positive.handle
                },
                "most_engaging": {
                    "content": most_engaging.content,
                    "likes": most_engaging.likes,
                    "retweets": most_engaging.retweets,
                    "category": most_engaging.hazard_category,
                    "handle": most_engaging.handle
                }
            }
        }
    
    def save_results(self, tweets: List[OceanHazardTweet], filename_prefix: str = "ocean_hazard"):
        """Save results to JSON and CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed tweet data to JSON
        json_filename = f"{filename_prefix}_tweets_{timestamp}.json"
        tweet_dicts = []
        for tweet in tweets:
            tweet_dicts.append({
                'username': tweet.username,
                'handle': tweet.handle,
                'content': tweet.content,
                'timestamp': tweet.timestamp,
                'retweets': tweet.retweets,
                'likes': tweet.likes,
                'replies': tweet.replies,
                'tweet_id': tweet.tweet_id,
                'matched_keywords': tweet.matched_keywords,
                'sentiment_score': tweet.sentiment_score,
                'sentiment_label': tweet.sentiment_label,
                'confidence': tweet.confidence,
                'hazard_category': tweet.hazard_category,
                'source': tweet.source
            })
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(tweet_dicts, f, indent=2, ensure_ascii=False)
        
        # Save to CSV for easy analysis
        csv_filename = f"{filename_prefix}_analysis_{timestamp}.csv"
        df = pd.DataFrame(tweet_dicts)
        df.to_csv(csv_filename, index=False)
        
        # Save sentiment report
        report_filename = f"{filename_prefix}_report_{timestamp}.json"
        report = self.generate_sentiment_report(tweets)
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved:")
        logger.info(f"  📄 Tweet data: {json_filename}")
        logger.info(f"  📊 CSV analysis: {csv_filename}")
        logger.info(f"  📈 Sentiment report: {report_filename}")
        
        return json_filename, csv_filename, report_filename

def display_tweets(tweets: List[OceanHazardTweet], limit: int = 5):
    """Display tweets in a formatted way"""
    print(f"\n{'='*80}")
    print(f"🌊 OCEAN HAZARD TWEETS ANALYSIS")
    print(f"{'='*80}")
    
    for i, tweet in enumerate(tweets[:limit], 1):
        # Sentiment emoji
        sentiment_emoji = {"positive": "😊", "negative": "😰", "neutral": "😐"}
        emoji = sentiment_emoji.get(tweet.sentiment_label, "🤔")
        
        print(f"\n{i}. {emoji} @{tweet.handle} ({tweet.sentiment_label.upper()}: {tweet.sentiment_score:.2f})")
        print(f"   📂 Category: {tweet.hazard_category.upper()}")
        print(f"   🏷️  Keywords: {', '.join(tweet.matched_keywords)}")
        print(f"   💬 {tweet.content}")
        print(f"   📊 ❤️{tweet.likes} | 🔄{tweet.retweets} | 💬{tweet.replies}")
        print(f"   🕒 {tweet.timestamp}")
        print("-" * 80)

def main():
    """Main execution function"""
    print("🚀 Starting Ocean Hazard Sentiment Analysis...")
    print(f"📋 Monitoring {len(KEYWORDS)} primary keywords and {len(EXTENDED_KEYWORDS)} extended keywords")
    
    # Initialize analyzer
    analyzer = OceanHazardAnalyzer()
    
    # Search for tweets
    start_time = time.time()
    tweets = analyzer.search_ocean_hazards()
    search_time = time.time() - start_time
    
    print(f"\n⚡ Analysis completed in {search_time:.2f} seconds!")
    print(f"📊 Found {len(tweets)} ocean hazard tweets")
    
    if tweets:
        # Display sample tweets
        display_tweets(tweets, limit=8)
        
        # Generate and display report
        print(f"\n{'='*80}")
        print("📈 SENTIMENT ANALYSIS REPORT")
        print(f"{'='*80}")
        
        report = analyzer.generate_sentiment_report(tweets)
        
        # Summary statistics
        summary = report['summary']
        print(f"\n📊 OVERALL STATISTICS:")
        print(f"   Total Tweets: {summary['total_tweets']}")
        print(f"   Average Sentiment: {summary['avg_sentiment_score']:.3f}")
        print(f"   Total Likes: {summary['total_engagement']['likes']:,}")
        print(f"   Total Retweets: {summary['total_engagement']['retweets']:,}")
        print(f"   Total Replies: {summary['total_engagement']['replies']:,}")
        
        # Sentiment distribution
        print(f"\n💭 SENTIMENT DISTRIBUTION:")
        for sentiment, count in summary['sentiment_distribution'].items():
            percentage = (count / summary['total_tweets']) * 100
            print(f"   {sentiment.upper()}: {count} tweets ({percentage:.1f}%)")
        
        # Category breakdown
        print(f"\n🌊 HAZARD CATEGORIES:")
        categories = report['by_hazard_category']
        for category, data in sorted(categories.items(), key=lambda x: x[1]['total_tweets'], reverse=True):
            print(f"   {category.upper()}: {data['total_tweets']} tweets (avg sentiment: {data['avg_sentiment_score']:.2f})")
        
        # Top keywords
        print(f"\n🔍 TOP KEYWORDS:")
        for keyword, count in list(report['top_keywords'].items())[:10]:
            print(f"   {keyword}: {count} mentions")
        
        # Notable tweets
        notable = report['notable_tweets']
        print(f"\n🎯 NOTABLE TWEETS:")
        print(f"   😰 MOST NEGATIVE ({notable['most_negative']['score']:.2f}): @{notable['most_negative']['handle']}")
        print(f"      {notable['most_negative']['content'][:100]}...")
        print(f"   😊 MOST POSITIVE ({notable['most_positive']['score']:.2f}): @{notable['most_positive']['handle']}")  
        print(f"      {notable['most_positive']['content'][:100]}...")
        print(f"   🔥 MOST ENGAGING ({notable['most_engaging']['likes']} likes): @{notable['most_engaging']['handle']}")
        print(f"      {notable['most_engaging']['content'][:100]}...")
        
        # Save results
        print(f"\n💾 Saving results...")
        json_file, csv_file, report_file = analyzer.save_results(tweets)
        
        print(f"\n✅ Analysis complete! Files saved successfully.")
        print(f"📁 Open '{csv_file}' in Excel for detailed analysis")
        
    else:
        print("❌ No tweets found.")

if __name__ == '__main__':
    main()