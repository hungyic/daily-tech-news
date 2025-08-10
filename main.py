import os
import asyncio
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import feedparser
import requests
import google.generativeai as genai
from pathlib import Path

class TechNewsBot:
    def __init__(self):
        # 初始化 Gemini
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("請設置 GEMINI_API_KEY 環境變數")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 新聞來源
        self.news_sources = {
            "TechCrunch": "https://techcrunch.com/feed/",
            "The Verge": "https://www.theverge.com/rss/index.xml",
            "Ars Technica": "http://feeds.arstechnica.com/arstechnica/index",
            "Wired": "https://www.wired.com/feed/rss",
            "MIT Technology Review": "https://www.technologyreview.com/feed/",
            "Hacker News": "https://hnrss.org/frontpage",
            "IEEE Spectrum": "https://spectrum.ieee.org/rss"
        }
        
        # 創建報告目錄
        Path("reports").mkdir(exist_ok=True)
    
    def fetch_recent_news(self, hours_back=24):
        """獲取最近的新聞"""
        print(f"🔍 開始獲取過去 {hours_back} 小時的新聞...")
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        all_news = []
        
        for source_name, url in self.news_sources.items():
            try:
                print(f"📰 正在獲取 {source_name} 新聞...")
                feed = feedparser.parse(url)
                source_count = 0
                
                for entry in feed.entries:
                    try:
                        # 處理不同的時間格式
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = datetime(*entry.published_parsed[:6])
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                            pub_date = datetime(*entry.updated_parsed[:6])
                        else:
                            pub_date = datetime.now()
                        
                        if pub_date >= cutoff_time:
                            news_item = {
                                "title": entry.title,
                                "link": entry.link,
                                "summary": getattr(entry, 'summary', entry.title)[:300],  # 限制摘要長度
                                "published": pub_date.isoformat(),
                                "source": source_name
                            }
                            all_news.append(news_item)
                            source_count += 1
                    except Exception as e:
                        continue
                
                print(f"✅ {source_name}: {source_count} 篇新聞")
                        
            except Exception as e:
                print(f"❌ {source_name} 獲取失敗: {e}")
                continue
        
        # 按時間排序，取最新的 50 篇
        all_news.sort(key=lambda x: x['published'], reverse=True)
        all_news = all_news[:50]  # 限制數量避免 API 超限
        
        print(f"🎉 總共獲取 {len(all_news)} 篇新聞")
        return all_news
    
    def categorize_news(self, news_items):
        """新聞智能分類"""
        categories = {
            "🤖 人工智慧與機器學習": [],
            "🔒 資訊安全": [],
            "☁️ 雲端與基礎設施": [],
            "💻 軟體開發": [],
            "🚀 新創與投資": [],
            "📱 消費性科技": [],
            "🔬 科學研究": [],
            "📰 其他科技新聞": []
        }
        
        # 更精確的關鍵字分類
        keywords_map = {
            "🤖 人工智慧與機器學習": [
                "ai", "artificial intelligence", "machine learning", "neural", "gpt", 
                "claude", "openai", "deepmind", "llm", "chatbot", "transformer", 
                "deep learning", "computer vision", "natural language"
            ],
            "🔒 資訊安全": [
                "security", "breach", "hack", "vulnerability", "cyber", "malware", 
                "encryption", "privacy", "ransomware", "phishing", "zero-day", "exploit"
            ],
            "☁️ 雲端與基礎設施": [
                "cloud", "aws", "azure", "gcp", "docker", "kubernetes", "serverless", 
                "microservices", "devops", "infrastructure"
            ],
            "💻 軟體開發": [
                "programming", "developer", "code", "github", "open source", "framework", 
                "api", "software", "javascript", "python", "react", "node"
            ],
            "🚀 新創與投資": [
                "startup", "funding", "investment", "ipo", "acquisition", "venture", 
                "business", "unicorn", "valuation"
            ],
            "📱 消費性科技": [
                "iphone", "android", "smartphone", "tablet", "wearable", "consumer", 
                "apple", "samsung", "google pixel"
            ],
            "🔬 科學研究": [
                "research", "study", "paper", "university", "breakthrough", "discovery", 
                "journal", "peer review"
            ]
        }
        
        for item in news_items:
            text = f"{item['title']} {item['summary']}".lower()
            categorized = False
            
            # 計算每個分類的匹配分數
            category_scores = {}
            for category, keywords in keywords_map.items():
                score = sum(1 for keyword in keywords if keyword in text)
                if score > 0:
                    category_scores[category] = score
            
            # 選擇分數最高的分類
            if category_scores:
                best_category = max(category_scores, key=category_scores.get)
                categories[best_category].append(item)
                categorized = True
            
            if not categorized:
                categories["📰 其他科技新聞"].append(item)
        
        # 只保留有新聞的分類，並限制每類新聞數量
        filtered_categories = {}
        for category, news_list in categories.items():
            if news_list:
                # 每個分類最多保留 8 篇新聞
                filtered_categories[category] = news_list[:8]
        
        return filtered_categories
    
    async def generate_report(self, categorized_news):
        """使用 Gemini 生成專業報告"""
        print("🤖 正在使用 Gemini 生成報告...")
        
        # 計算總新聞數
        total_news = sum(len(news_list) for news_list in categorized_news.values())
        
        prompt = f"""
請根據以下 {total_news} 篇分類科技新聞，生成一份專業的每日科技新聞摘要報告。

新聞數據：
{json.dumps(categorized_news, indent=2, ensure_ascii=False)}

請嚴格按照以下格式生成報告：

# 📰 每日科技新聞摘要
*生成時間：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}*

---

## 🌟 今日重點
請從所有新聞中挑選 3-4 個最重要或最有趣的新聞，每個用 2-3 句話說明為什麼重要。

---

## 📊 分類新聞詳情

請對每個有新聞的分類：
1. 先用 1-2 句話概述該領域今日的主要發展
2. 列出該分類的新聞，每則包含：
   - **標題**：[新聞標題]
   - **摘要**：用 2-3 句話總結要點
   - **來源**：[來源網站]
   - **連結**：[原文網址]
   - **重要度**：⭐-⭐⭐⭐⭐⭐ (1-5顆星)

---

## 🔮 趨勢觀察
基於今日新聞，用 3-4 句話分析當前科技發展趨勢和值得關注的方向。

---

請用繁體中文撰寫，保持專業但易讀的語調。確保每個新聞都包含原文連結。
        """
        
        try:
            response = self.model.generate_content(prompt)
            print("✅ 報告生成成功")
            return response.text
        except Exception as e:
            print(f"❌ Gemini API 調用失敗: {e}")
            return self.generate_fallback_report(categorized_news)
    
    def generate_fallback_report(self, categorized_news):
        """備用的簡單報告生成"""
        print("🔄 使用備用方案生成報告...")
        
        report = f"""# 📰 每日科技新聞摘要
*生成時間：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}*

---

"""
        
        for category, news_list in categorized_news.items():
            if news_list:
                report += f"## {category}\n\n"
                for i, news in enumerate(news_list[:5], 1):
                    report += f"### {i}. {news['title']}\n"
                    report += f"- **來源**: {news['source']}\n"
                    report += f"- **連結**: [閱讀原文]({news['link']})\n"
                    report += f"- **摘要**: {news['summary'][:150]}...\n\n"
                report += "---\n\n"
        
        return report
    
    def send_email(self, report_content):
        """發送郵件報告"""
        print("📧 正在發送郵件...")
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = os.getenv('FROM_EMAIL')
            msg['To'] = os.getenv('TO_EMAIL')
            msg['Subject'] = f"📰 每日科技新聞摘要 - {datetime.now().strftime('%Y-%m-%d')}"
            
            # 轉換為 HTML
            html_content = self.markdown_to_html(report_content)
            
            # 添加純文字版本
            text_part = MIMEText(report_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # 發送郵件
            with smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT', 587))) as server:
                server.starttls()
                server.login(os.getenv('EMAIL_USERNAME'), os.getenv('EMAIL_PASSWORD'))
                server.send_message(msg)
            
            print("✅ 郵件發送成功！")
            return True
            
        except Exception as e:
            print(f"❌ 郵件發送失敗: {e}")
            return False
    
    def markdown_to_html(self, markdown_content):
        """Markdown 轉 HTML"""
        html = markdown_content
        
        # 基本轉換
        html = html.replace('# ', '<h1>').replace('\n## ', '</h1>\n<h2>')
        html = html.replace('\n### ', '</h2>\n<h3>').replace('\n---', '</h3>\n<hr>')
        html = html.replace('**', '<strong>').replace('**', '</strong>')
        html = html.replace('*', '<em>').replace('*', '</em>')
        html = html.replace('\n- ', '<br>• ')
        
        # 添加樣式
        styled_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ 
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; 
            line-height: 1.6; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px;
            color: #333;
        }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; border-bottom: 2px solid #ecf0f1; margin-top: 30px; }}
        h3 {{ color: #2c3e50; }}
        hr {{ border: none; height: 1px; background: #ecf0f1; margin: 20px 0; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .emoji {{ font-size: 1.2em; }}
        strong {{ color: #2c3e50; }}
        .footer {{ margin-top: 40px; text-align: center; color: #7f8c8d; font-size: 0.9em; }}
    </style>
</head>
<body>
    {html}
    <div class="footer">
        <hr>
        <p>🤖 此報告由 AI 自動生成 | 📧 每日定時發送</p>
    </div>
</body>
</html>
        """
        return styled_html
    
    def save_report(self, report_content):
        """儲存報告"""
        filename = f"reports/news_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"💾 報告已儲存至 {filename}")

async def main():
    print("🚀 每日科技新聞摘要系統啟動")
    print("=" * 50)
    
    try:
        bot = TechNewsBot()
        
        # 獲取新聞
        news_items = bot.fetch_recent_news(hours_back=24)
        if not news_items:
            print("❌ 沒有獲取到任何新聞，程序結束")
            return
        
        # 分類新聞
        categorized_news = bot.categorize_news(news_items)
        print(f"📊 新聞分類完成，共 {len(categorized_news)} 個分類")
        
        # 生成報告
        report = await bot.generate_report(categorized_news)
        
        # 儲存報告
        bot.save_report(report)
        
        # 發送郵件
        success = bot.send_email(report)
        
        if success:
            print("🎉 任務完成！新聞報告已成功生成並發送")
        else:
            print("⚠️  報告生成完成，但郵件發送失敗")
            
    except Exception as e:
        print(f"❌ 程序執行出錯: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
