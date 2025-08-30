import asyncio
import datetime
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def save_report(content: str):
    """将内容保存为带日期的Markdown文件"""
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

async def main():
    server_params = StdioServerParameters(
        command='uv',
        args=['run', 'mcp.py'],
    )

    print("🚀 正在启动并连接到 MCP AI 新闻服务...")
    try:
        async with stdio_client(server_params) as (stdio, write):
            async with ClientSession(stdio, write) as session:
                await session.initialize()
                print("✅ 连接成功！")

                print("\n🤖 正在调用 'generate_ai_news_report' 工具，请稍候...")
                response = await session.call_tool('generate_ai_news_report', {})
                report_content = response.content[0].text
                
                print("\n📄 已收到报告内容，正在保存文件...")
                save_report(report_content)

    except Exception as e:
        print(f"\n❌ 客户端运行出错: {e}")

if __name__ == '__main__':
    asyncio.run(main())
