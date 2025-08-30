import os
import asyncio
import feedparser
from openai import AsyncOpenAI
from dotenv import load_dotenv
from mcp.server import FastMCP
import math

# --- 配置 ---
load_dotenv()

# 从环境变量加载配置
API_KEY = os.environ.get("OPENAI_API_KEY")
API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")

# RSS Feed
RSS_FEEDS = {
    "HackerNews": "https://news.ycombinator.com/rss",
    "OpenAI": "https://openai.com/news/rss.xml",
    "arXiv cs.AI": "https://rss.arxiv.org/rss/cs.AI",
    "arXiv cs.LG": "https://rss.arxiv.org/rss/cs.LG",
}

MAX_ITEMS_PER_FEED = 75 # 每个源最多获取的新闻条数
CHUNK_SIZE = 25 # 每次请求 LLM 处理的新闻条数

# --- 初始化 MCP 应用 ---
app = FastMCP('ai-news-reporter')

# --- 辅助函数 ---
def get_rss_entries() -> list:
    """同步函数：从所有 RSS 源获取新闻条目。"""
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

def build_prompt(entries_chunk: list) -> str:
    """为单个新闻块构建Prompt。"""
    formatted_entries = []
    for i, entry in enumerate(entries_chunk):
        summary_text = entry['summary'].replace('<p>', '').replace('</p>', '').replace('\n', ' ').strip()
        formatted_entries.append(
            f"ID:{i+1}\n来源:{entry['source']}\n标题:{entry['title']}\n链接:{entry['link']}\n摘要:{summary_text}\n---"
        )
    entries_text = "\n".join(formatted_entries)
    return f"""
请分析以下从多个来源获取的科技新闻列表。你的任务是：
1. **筛选**：只选择与人工智能（AI）领域直接相关，并且是「重大」或具有「创新性」的新闻。请严格过滤掉无关、琐碎、无明确贡献或重复的新闻。
2. **生成详细摘要**：对于筛选出的每一条重要新闻，用专业但易于理解的中文，撰写一段**详细的摘要**（约200-300字），深入解释其**核心背景、关键方法、创新点、以及最终取得的成果或其潜在影响**。
3. **排序**：将筛选出的新闻按照其重要性和影响力从高到低进行排序。
4. **输出格式**：请严格按照以下Markdown格式输出。**不要包含原文链接**。不要添加任何额外的解释或开场白。

### [新闻标题]
- **来源**: [来源名称]
- **摘要**: [你撰写的详细中文摘要]

---
以下是待处理的新闻列表：
{entries_text}
"""

async def call_openai_api(client: AsyncOpenAI, prompt: str, chunk_index: int, total_chunks: int) -> str | None:
    """异步调用 OpenAI API。"""
    print(f"\n🧠 正在处理第 {chunk_index + 1}/{total_chunks} 块数据，连接 LLM API...")
    print(f"   - API接入点: {API_BASE}")
    print(f"   - 使用模型: {MODEL_NAME}")
    try:
        response = await client.chat.completions.create(
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

@app.tool()
async def generate_ai_news_report() -> str:
    """
    获取最新的AI相关RSS新闻，通过大模型进行分析、筛选和总结，并生成一份Markdown格式的AI新闻日报。

    Returns:
        一份包含最新AI新闻摘要的Markdown格式字符串。
    """
    # 0. 检查 API Key
    if not API_KEY or API_KEY == "YOUR_OPENAI_API_KEY_HERE":
        error_msg = "❌ API Key 未设置。请在服务端环境的 .env 文件中进行配置。"
        print(error_msg)
        return error_msg
    
    # 1. 获取所有新闻条目 (在异步函数中运行同步代码)
    loop = asyncio.get_running_loop()
    entries = await loop.run_in_executor(None, get_rss_entries)
    if not entries:
        msg = "\n❌ 未能获取到任何新闻，无法生成报告。"
        print(msg)
        return msg
        
    total_entries = len(entries)
    print(f"\n📊 共获取到 {total_entries} 条新闻条目。")

    # 2. 分块处理
    num_chunks = math.ceil(total_entries / CHUNK_SIZE)
    print(f"   - 将数据分为 {num_chunks} 块进行处理 (每块 {CHUNK_SIZE} 条)。")
    
    # 初始化异步 OpenAI 客户端
    client = AsyncOpenAI(api_key=API_KEY, base_url=API_BASE)
    
    # 并发处理所有块
    tasks = []
    for i in range(num_chunks):
        start_index = i * CHUNK_SIZE
        end_index = start_index + CHUNK_SIZE
        chunk = entries[start_index:end_index]
        prompt = build_prompt(chunk)
        tasks.append(call_openai_api(client, prompt, i, num_chunks))
    
    processed_results = await asyncio.gather(*tasks)
    
    # 3. 合并结果并返回
    final_content_parts = [res for res in processed_results if res]
    if not final_content_parts:
        msg = "\n❌ 所有块均未能成功处理，无法生成报告。"
        print(msg)
        return msg

    full_report_content = "\n".join(final_content_parts)
    print("\n✅ 所有块处理完毕，报告已生成。")
    return full_report_content

if __name__ == "__main__":
    app.run(transport='stdio')
