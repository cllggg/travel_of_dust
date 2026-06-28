#!/usr/bin/env python3
"""
《灰尘的旅行》全书插画批量生成引擎 v3.0
出版级纯净插画：10-20岁青少年科普读物标准
纯图像表达主题，无任何文字，形象生动，逻辑严谨，内容准确
风格：1950年代中国经典少儿科普读物插画，丰子恺式木刻水彩
"""
import requests
import base64
import json
from pathlib import Path
import re

API_URL = 'http://192.168.2.128:7860/sdapi/v1/txt2img'
OUTPUT_DIR = Path("images")
OUTPUT_DIR.mkdir(exist_ok=True)

STYLE_PRESET = """经典少儿科普读物插画，1950年代复古科学教科书风格，丰子恺式木刻淡彩画，米黄色纸张质感。
适合10-20岁青少年阅读，形象生动具体，场景真实合理，严格遵循现实科学逻辑。
画面中心主题明确突出，构图清晰，叙事性强，用画面讲故事，不需要任何文字解释。
画风：手绘线条清晰，色彩柔和温暖，人物形象可爱亲切，不恐怖，造型准确。
色彩：暖米色调背景，搭配天蓝色、草绿色、赭石色、珊瑚色等柔和自然色彩，整体和谐统一。
极高品质，画面干净，艺术感强，教育性与艺术性兼备，正式出版物质量。
【绝对禁止】画面中出现任何文字、数字、字母、符号、标签、框线、边框、标注线、气泡、签名、水印、标志，完全没有任何文字，所有信息通过画面形象表达。
"""

NEGATIVE_PROMPT = """文字，中文，英文，日文，韩文，任何文字，字体，书法，数字，符号，标签，标题，字幕，签名，水印，logo，
乱码，胡写乱画，像文字的涂鸦，假文字，无意义笔画，
对话框，思想泡泡，方框，边框，标注线，指向物体的线条，
照片写实，3D渲染，CGI，日式动漫，丑陋，变形，模糊，低质量，扭曲，多手指，恶心，恐怖，血腥，
霓虹色，亮光塑料质感，现代赛博风格，抽象艺术，多余元素"""

def generate_illustration(chapter_config, overwrite=False):
    out_path = OUTPUT_DIR / chapter_config["file"]
    if out_path.exists() and not overwrite:
        print(f"  ⏭️  已存在，跳过: {out_path.name}")
        return True
    
    prompt = STYLE_PRESET + "\n\n内容：" + chapter_config["prompt"]
    
    r = requests.post(API_URL, json={
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "steps": 10,
        "width": 1024,
        "height": 768,
        "guidance_scale": 2.5,
        "seed": chapter_config.get("seed", -1),
        "sampler": "UniPC Trailing"
    }, timeout=600)
    
    img_data = base64.b64decode(r.json()["images"][0])
    with open(out_path, "wb") as f:
        f.write(img_data)
    print(f"  ✓ 生成完成: {out_path.name} ({len(img_data)//1024}KB)")
    return True

def insert_into_markdown(chapter_config):
    md_path = Path(chapter_config["markdown_file"])
    if not md_path.exists():
        print(f"  ✗ 未找到Markdown文件: {md_path.name}")
        return False
    
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    img_tag = f'<div align="center">\n\n![{chapter_config["title"]}](images/{chapter_config["file"]})\n\n</div>\n\n### 📍 本章导航'
    
    if '<div align="center">' in content and '本章导航' in content:
        content = re.sub(
            r'<div align="center">.*?</div>\s*### 📍 本章导航',
            img_tag,
            content,
            flags=re.DOTALL
        )
    else:
        content = content.replace("### 📍 本章导航", img_tag)
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ 已插入到: {md_path.name}")
    return True

def process_chapter(chapter, overwrite=False):
    print(f"\n{'='*60}")
    print(f"📖 {chapter['title']}")
    print(f"{'='*60}")
    try:
        generate_illustration(chapter, overwrite=overwrite)
        insert_into_markdown(chapter)
        return True
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return False

if __name__ == "__main__":
    import sys
    overwrite = "--overwrite" in sys.argv
    config_file = [f for f in sys.argv[1:] if not f.startswith("--")][0] if len(sys.argv) > 1 else "chapters_v2.json"
    with open(config_file, "r", encoding="utf-8") as f:
        chapters = json.load(f)
    print(f"🚀 开始生成 {len(chapters)} 章出版级插画...")
    success = 0
    for i, ch in enumerate(chapters, 1):
        print(f"\n进度: {i}/{len(chapters)}")
        if process_chapter(ch, overwrite=overwrite):
            success += 1
    print(f"\n{'='*60}")
    print(f"✅ 全部完成！成功 {success}/{len(chapters)} 章")
    print(f"{'='*60}")
