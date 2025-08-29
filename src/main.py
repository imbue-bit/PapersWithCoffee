import os
import datetime
import feedparser
import openai
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

RSS_FEEDS = {
    "HackerNews": "https://news.ycombinator.com/rss",
    "OpenAI": "https://openai.com/news/rss.xml",
    "arXiv cs.AI": "https://rss.arxiv.org/rss/cs.AI",
    "arXiv cs.LG": "https://rss.arxiv.org/rss/cs.LG",
}

MAX_ITEMS_PER_FEED = 1024

def get_rss_entries():
    all_entries = []
    print("🔍 正在从以下源获取新闻...")
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            print(f"  - {name}: 成功获取 {len(feed.entries)} 条新闻")
            entries = feed.entries[:MAX_ITEMS_PER_FEED]
            for entry in entries:
                all_entries.append({
                    "source": name,
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get("summary", "")
                })
        except Exception as e:
            print(f"  - {name}: 获取失败，错误: {e}")
    return all_entries

def call_openai_api(prompt):
    if API_KEY == "YOUR_OPENAI_API_KEY_HERE" or not API_KEY:
        raise ValueError("❌ API Key 未设置。请在代码中或 .env 文件中进行配置。")

    print("\n🧠 正在连接 LLM API，请稍候...")
    print(f"   - API接入点: {API_BASE}")
    print(f"   - 使用模型: {MODEL_NAME}")

    try:
        client = openai.OpenAI(api_key=API_KEY, base_url=API_BASE)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一位专业的AI领域分析师和科技编辑。你的任务是分析、筛选、总结并以中文新闻风格呈现重要的AI进展。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=4000,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"\n❌ API 调用失败: {e}")
        return None

def build_prompt(entries):
    """构建用于筛选、摘要和翻译的Prompt"""
    formatted_entries = []
    for i, entry in enumerate(entries):
        # 清理摘要中的HTML标签
        summary_text = entry['summary'].replace('<p>', '').replace('</p>', '').replace('\n', ' ').strip()
        formatted_entries.append(
            f"ID:{i+1}\n来源:{entry['source']}\n标题:{entry['title']}\n链接:{entry['link']}\n摘要:{summary_text}\n---"
        )
    
    entries_text = "\n".join(formatted_entries)

    prompt = f"""
请分析以下从多个来源获取的科技新闻列表。你的任务是：

1.  **筛选**：只选择与人工智能（AI）领域直接相关，并且是「重大」或具有「创新性」的新闻。请严格过滤掉以下内容：
    *   与AI无关的技术新闻（如普通的软件更新、Web开发技巧）。
    *   非常琐碎的AI应用（例如：使用现有机器学习模型预测学生退学、预测股价等没有方法论创新的简单应用）。
    *   没有明确技术或研究贡献的讨论或观点。
    *   重复的或非常相似的新闻。

2.  **摘要和翻译**：对于筛选出的每一条重要新闻：
    *   用专业但易于理解的中文，撰写一段约100-200字的摘要。
    *   摘要应清晰地说明这项工作解决了什么问题、使用了什么核心方法、取得了什么关键成果或意义。

3.  **排序**：将筛选出的新闻按照其重要性和影响力从高到低进行排序。

4.  **输出格式**：请严格按照以下Markdown格式输出，不要添加任何额外的解释或开场白。

### 标题
- **来源**: [来源名称]
- **摘要**: [你撰写的中文摘要]
- **链接**: [原文链接]

---

以下是待处理的新闻列表：

{entries_text}
"""
    return prompt

def generate_markdown_report(content):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"PapersWithCode_AI_日报_{today_str}.md"
    
    header = f"""
# PapersWithCode AI 日报

**日期**: {today_str}

---

"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write(content)
        
    print(f"\n✅ 报告生成成功！文件已保存为: {filename}")

def main():
    print("="*50)
    print("📰 PapersWithCode AI 日报 📰")
    print("="*50)

    entries = get_rss_entries()
    if not entries:
        print("\n❌ 未能获取到任何新闻，程序退出。")
        return
    print(f"\n📊 共获取到 {len(entries)} 条新闻条目，准备进行AI分析...")
    prompt = build_prompt(entries)
    processed_content = call_openai_api(prompt)
    if processed_content:
        generate_markdown_report(processed_content)
    else:
        print("\n❌ 未能从API获取到处理结果，无法生成报告。")

if __name__ == "__main__":
    main()
