import sys, os, asyncio
sys.path.insert(0, 'backend')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONLEGACYWindowsConsoleIO'] = '1'

import builtins
_orig_print = builtins.print
def patched_print(*args, **kwargs):
    try: _orig_print(*args, **kwargs)
    except UnicodeEncodeError: pass
builtins.print = patched_print

async def test():
    from backend.services.radar_service.push_generator import generate_daily_summary_html

    html = await generate_daily_summary_html()
    print(f'Total HTML length: {len(html)}')

    # Check how many keyword blocks
    import re
    blocks = re.findall(r'<details[^>]*>', html)
    print(f'Number of <details> tags: {len(blocks)}')

    # Check ai_summary
    m = re.search(r'ai_summary[^>]*>(.*?)</p>', html, re.DOTALL)
    if m:
        summary = m.group(1)[:100]
        print(f'AI summary: {summary}')

asyncio.run(test())