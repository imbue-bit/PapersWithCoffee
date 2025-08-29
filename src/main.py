import os
import datetime
import feedparser
import openai
from dotenv import load_dotenv
import math

load_dotenv()

API_KEY = os.environ.get("OPENAI_API_KEY")
API_BASE = os.environ.get("OPENAI_API_BASE")
MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME")

RSS_FEEDS = {
    "HackerNews": "https://news.ycombinator.com/rss",
    "OpenAI": "https://openai.com/news/rss.xml",
    "arXiv cs.AI": "https://rss.arxiv.org/rss/cs.AI",
    "arXiv cs.LG": "https://rss.arxiv.org/rss/cs.LG",
}

MAX_ITEMS_PER_FEED = 75
CHUNK_SIZE = 25

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

def call_openai_api(prompt, chunk_index, total_chunks):
    if API_KEY == "YOUR_OPENAI_API_KEY_HERE" or not API_KEY:
        raise ValueError("❌ API Key 未设置。请在代码中或 .env 文件中进行配置。")

    print(f"\n🧠 正在处理第 {chunk_index + 1}/{total_chunks} 块数据，连接 LLM API...")
    print(f"   - API接入点: {API_BASE}")
    print(f"   - 使用模型: {MODEL_NAME}")

    try:
        client = openai.OpenAI(api_key=API_KEY, base_url=API_BASE)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一位专业的AI领域分析师和科技编辑。你的任务是分析、筛选、总结并以中文新闻风格呈现重要的AI进展。请严格按照用户指定的格式输出，不要添加任何额外内容。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=4000,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"\n❌ API 调用失败 (块 {chunk_index + 1}): {e}")
        return None

def build_prompt(entries_chunk):
    """
    为单个新闻块构建Prompt。
    """
    formatted_entries = []
    for i, entry in enumerate(entries_chunk):
        # 清理摘要中的HTML标签
        summary_text = entry['summary'].replace('<p>', '').replace('</p>', '').replace('\n', ' ').strip()
        formatted_entries.append(
            f"ID:{i+1}\n来源:{entry['source']}\n标题:{entry['title']}\n链接:{entry['link']}\n摘要:{summary_text}\n---"
        )
    
    entries_text = "\n".join(formatted_entries)

    prompt = f"""
请分析以下从多个来源获取的科技新闻列表。你的任务是：

1.  **筛选**：只选择与人工智能（AI）领域直接相关，并且是「重大」或具有「创新性」的新闻。请严格过滤掉无关、琐碎、无明确贡献或重复的新闻。

2.  **生成详细摘要**：对于筛选出的每一条重要新闻：
    *   用专业但易于理解的中文，撰写一段**详细的摘要**（约200-300字）。
    *   摘要必须深入解释这项工作的**核心背景、关键方法、创新点、以及最终取得的成果或其潜在影响**。目标是让读者即使不看原文也能充分理解其价值。

3.  **排序**：将筛选出的新闻按照其重要性和影响力从高到低进行排序。

4.  **输出格式 (为打印优化)**：请严格按照以下Markdown格式输出。**不要包含原文链接**，用详细摘要代替。不要添加任何额外的解释或开场白。

### [新闻标题]
- **来源**: [来源名称]
- **摘要**: [你撰写的详细中文摘要，详细说明背景、方法、成果和意义]

---

以下是待处理的新闻列表：

{entries_text}
"""
    return prompt

def generate_markdown_report(content):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"Coffee_日报_{today_str}.md"
    
    header = f"""# PapersWithCoffee 日报

**日期**: {today_str}
---

"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write(content)
        
    print(f"\n✅ 报告生成成功！文件已保存为: {filename}")

def main():
    print("="*50)
    print("📰 PapersWithCoffee 日报 📰")
    print("="*50)

    # 1. 获取所有新闻条目
    entries = get_rss_entries()
    if not entries:
        print("\n❌ 未能获取到任何新闻，程序退出。")
        return
    
    total_entries = len(entries)
    print(f"\n📊 共获取到 {total_entries} 条新闻条目。")

    # 2. 分块处理逻辑
    num_chunks = math.ceil(total_entries / CHUNK_SIZE)
    print(f"   - 将数据分为 {num_chunks} 块进行处理 (每块 {CHUNK_SIZE} 条)。")
    
    final_content_parts = []
    for i in range(num_chunks):
        # 创建当前块的数据
        start_index = i * CHUNK_SIZE
        end_index = start_index + CHUNK_SIZE
        chunk = entries[start_index:end_index]
        
        # 为当前块构建并调用API
        prompt = build_prompt(chunk)
        processed_chunk_content = call_openai_api(prompt, i, num_chunks)
        
        if processed_chunk_content:
            final_content_parts.append(processed_chunk_content)
            print(f"   - ✅ 第 {i + 1}/{num_chunks} 块处理成功。")
        else:
            print(f"   - ⚠️ 第 {i + 1}/{num_chunks} 块处理失败，跳过此块。")

    # 3. 合并所有块的结果并生成报告
    if final_content_parts:
        # 将所有成功处理的块的内容合并成一个字符串
        full_report_content = "\n".join(final_content_parts)
        print("\n📑 所有块处理完毕，正在合并生成最终报告...")
        generate_markdown_report(full_report_content)
    else:
        print("\n❌ 所有块均未能成功处理，无法生成报告。")


if __name__ == "__main__":
    main()
