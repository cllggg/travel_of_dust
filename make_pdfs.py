#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将《灰尘的旅行》Markdown 文件批量转为 PDF，并合并为整本书 PDF。

策略：
1. 用 `markdown` 库把每个 .md 文件解析为 HTML；
2. 用 BeautifulSoup 解析 HTML，递归生成 reportlab Flowable；
3. 使用 PingFang/STHeiti 中文字体；
4. 先为每个章节生成单独的 PDF 到 pdf/chapters/；
5. 再用 pypdf 把所有 PDF 合并为 灰尘的旅行-完整版.pdf。
"""

import os
import re
import sys
from pathlib import Path

import markdown
from bs4 import BeautifulSoup, NavigableString, Tag

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Image as RLImage,
    Table,
    TableStyle,
    KeepTogether,
    ListFlowable,
    ListItem,
    HRFlowable,
    Preformatted,
)

# ---------- 中文字体注册 ----------
FONT_CANDIDATES = [
    ("PingFang", "/System/Library/Fonts/PingFang.ttc"),  # macOS 自带
    ("STHeiti", "/System/Library/Fonts/STHeiti Medium.ttc"),
    ("STHeitiLight", "/System/Library/Fonts/STHeiti Light.ttc"),
    ("Songti", "/System/Library/Fonts/Songti.ttc"),
    ("HiraginoSansGB", "/Library/Fonts/Hiragino Sans GB.ttc"),
    ("NotoSerifCJK", "/System/Library/Fonts/NotoSerifCJK.ttc"),
    ("NotoSansCJK", "/System/Library/Fonts/NotoSansCJK.ttc"),
]

CJK_FONT_NAME = None
CJK_FONT_BOLD = None
for name, path in FONT_CANDIDATES:
    if os.path.exists(path):
        try:
            # TTC 字体文件需要 subfontIndex
            sub_index = 0
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=sub_index))
            CJK_FONT_NAME = name
            CJK_FONT_BOLD = name  # 用同款粗体
            print(f"使用字体: {name}  来源: {path}")
            break
        except Exception as e:
            print(f"注册字体失败 {name}: {e}")
            continue

if CJK_FONT_NAME is None:
    print("警告：未找到合适的中文字体，可能导致中文显示问题", file=sys.stderr)

# ---------- 路径配置 ----------
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "pdf"
CHAPTERS_DIR = OUT_DIR / "chapters"
CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

# 页面尺寸 & 边距
PAGE_W, PAGE_H = A4
LEFT_MARGIN = 2.2 * cm
RIGHT_MARGIN = 2.2 * cm
TOP_MARGIN = 2.2 * cm
BOTTOM_MARGIN = 2.2 * cm
USABLE_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN


# ---------- 样式 ----------
def make_styles():
    base = ParagraphStyle(
        name="Base",
        fontName=CJK_FONT_NAME or "Helvetica",
        fontSize=11,
        leading=18,
        textColor=colors.HexColor("#1f1f1f"),
        alignment=TA_JUSTIFY,
        wordWrap="CJK",
    )
    styles = {
        "base": base,
        "h1": ParagraphStyle(
            "H1",
            parent=base,
            fontSize=22,
            leading=32,
            spaceBefore=4,
            spaceAfter=14,
            textColor=colors.HexColor("#1a365d"),
            alignment=TA_LEFT,
            fontName=CJK_FONT_BOLD or CJK_FONT_NAME or "Helvetica-Bold",
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base,
            fontSize=17,
            leading=26,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#1a365d"),
            fontName=CJK_FONT_BOLD or CJK_FONT_NAME or "Helvetica-Bold",
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=base,
            fontSize=14,
            leading=22,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#2c5282"),
            fontName=CJK_FONT_BOLD or CJK_FONT_NAME or "Helvetica-Bold",
        ),
        "h4": ParagraphStyle(
            "H4",
            parent=base,
            fontSize=12,
            leading=20,
            spaceBefore=8,
            spaceAfter=4,
            textColor=colors.HexColor("#2c5282"),
            fontName=CJK_FONT_BOLD or CJK_FONT_NAME or "Helvetica-Bold",
        ),
        "p": ParagraphStyle(
            "P",
            parent=base,
            fontSize=11,
            leading=19,
            spaceAfter=8,
            firstLineIndent=2 * 12,  # 中文首行缩进 2 字符
        ),
        "p_noindent": ParagraphStyle(
            "PNoIndent",
            parent=base,
            fontSize=11,
            leading=19,
            spaceAfter=8,
        ),
        "blockquote": ParagraphStyle(
            "Blockquote",
            parent=base,
            fontSize=10.5,
            leading=18,
            leftIndent=14,
            rightIndent=6,
            spaceBefore=6,
            spaceAfter=6,
            textColor=colors.HexColor("#3d3d3d"),
            backColor=colors.HexColor("#f3f4f6"),
            borderColor=colors.HexColor("#cbd5e0"),
            borderWidth=0,
            borderPadding=8,
        ),
        "li": ParagraphStyle(
            "LI",
            parent=base,
            fontSize=11,
            leading=18,
            leftIndent=0,
            spaceAfter=2,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base,
            fontName="Courier",
            fontSize=9.5,
            leading=15,
            backColor=colors.HexColor("#f1f5f9"),
            leftIndent=8,
            rightIndent=8,
            spaceBefore=6,
            spaceAfter=6,
            borderColor=colors.HexColor("#cbd5e0"),
            borderWidth=0,
            borderPadding=6,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base,
            fontSize=9.5,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4a5568"),
            spaceAfter=10,
        ),
        "divider_label": ParagraphStyle(
            "Divider",
            parent=base,
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#718096"),
            spaceBefore=8,
            spaceAfter=8,
        ),
    }
    return styles


STYLES = make_styles()


# ---------- HTML → inline 段落文本 ----------
def parse_inline(node):
    """递归处理节点，把 block 元素转为 ReportLab 支持的 inline 标签字符串。"""
    if isinstance(node, NavigableString):
        text = str(node)
        # 转义 ReportLab 段落里的特殊字符
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return text

    if not isinstance(node, Tag):
        return ""

    name = node.name.lower() if node.name else ""
    inner = "".join(parse_inline(c) for c in node.children)

    if name in ("strong", "b"):
        return f"<b>{inner}</b>"
    if name in ("em", "i"):
        return f"<i>{inner}</i>"
    if name in ("u",):
        return f"<u>{inner}</u>"
    if name in ("del", "s", "strike"):
        return f"<strike>{inner}</strike>"
    if name == "br":
        return "<br/>"
    if name == "code":
        # 使用等宽字体显示
        return f'<font face="Courier">{inner}</font>'
    if name == "a":
        href = node.get("href", "")
        return f'<link href="{href}" color="#1a73e8"><u>{inner}</u></link>'
    if name == "img":
        alt = node.get("alt", "")
        return f'<font color="#718096">[{alt or "图片"}]</font>'

    # 其它标签保留内部文本
    return inner


# ---------- Block 转换 ----------
def render_blockquote(node, flowables, depth=1):
    """blockquote 渲染：每个内部段落直接渲染为带底色和缩进的 Paragraph，自然分页。"""
    bq_p = ParagraphStyle(
        "BlockquoteP",
        parent=STYLES["base"],
        fontSize=10.5,
        leading=18,
        leftIndent=12,
        rightIndent=6,
        spaceBefore=2,
        spaceAfter=2,
        textColor=colors.HexColor("#2d3748"),
        backColor=colors.HexColor("#f3f4f6"),
        borderColor=colors.HexColor("#1a365d"),
        borderWidth=0,
        borderPadding=(4, 8, 4, 14),
    )
    bq_p_noindent = ParagraphStyle(
        "BlockquotePNoIndent",
        parent=bq_p,
        firstLineIndent=0,
    )

    flowables.append(Spacer(1, 4))
    for child in node.children:
        if isinstance(child, NavigableString):
            txt = str(child).strip()
            if not txt:
                continue
            txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables.append(Paragraph(txt, bq_p_noindent))
            continue
        if not isinstance(child, Tag):
            continue
        cname = (child.name or "").lower()
        if cname == "p":
            text = parse_inline(child).strip()
            if not text:
                continue
            flowables.append(Paragraph(text, bq_p))
        elif cname in ("h1", "h2", "h3", "h4", "h5", "h6"):
            # 引用块里的标题也用 bq 样式
            text = parse_inline(child).strip()
            if not text:
                continue
            head_style = ParagraphStyle(
                "BqHead", parent=bq_p, fontSize=12, leading=18, spaceBefore=4, spaceAfter=2,
                textColor=colors.HexColor("#1a365d"),
            )
            flowables.append(Paragraph(text, head_style))
        elif cname in ("ul", "ol"):
            # 列表：每项独立 paragraph，便于分页
            for li in child.find_all("li", recursive=False):
                t = parse_inline(li).strip()
                if t:
                    flowables.append(Paragraph(t, bq_p_noindent))
        elif cname == "blockquote":
            render_blockquote(child, flowables, depth + 1)
        elif cname == "img":
            render_image(child, flowables, BASE_DIR)
        else:
            t = child.get_text(" ", strip=True)
            if t:
                flowables.append(Paragraph(
                    t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                    bq_p_noindent,
                ))
    flowables.append(Spacer(1, 6))


def render_image(node, flowables, base_path: Path):
    src = node.get("src", "")
    if not src:
        return
    # 解析相对路径
    img_path = (base_path / src).resolve() if not os.path.isabs(src) else Path(src)
    if not img_path.exists():
        # 退化：直接基于工作目录
        img_path = (BASE_DIR / src).resolve()
    if not img_path.exists():
        # 找不到图：占位文本
        flowables.append(
            Paragraph(
                f'<font color="#c53030">[图片缺失：{src}]</font>', STYLES["caption"]
            )
        )
        return

    try:
        # 计算图片缩放
        from reportlab.lib.utils import ImageReader

        ir = ImageReader(str(img_path))
        iw, ih = ir.getSize()
        max_w = USABLE_W
        max_h = 16 * cm
        ratio = min(max_w / iw, max_h / ih, 1.0)
        w = iw * ratio
        h = ih * ratio
        img = RLImage(str(img_path), width=w, height=h)
        img.hAlign = "CENTER"
        flowables.append(Spacer(1, 6))
        flowables.append(img)
        alt = node.get("alt", "")
        if alt:
            flowables.append(
                Paragraph(alt, STYLES["caption"])
            )
        flowables.append(Spacer(1, 6))
    except Exception as e:
        flowables.append(
            Paragraph(
                f'<font color="#c53030">[图片加载失败：{src} | {e}]</font>',
                STYLES["caption"],
            )
        )


def render_list(node, flowables, ordered: bool, indent_extra: int = 0):
    """处理 ul/ol 列表。"""
    items = []
    for li in node.find_all("li", recursive=False):
        # 段落文本
        para = Paragraph(parse_inline(li), STYLES["li"])
        items.append(ListItem(para, leftIndent=14 + indent_extra))
    if items:
        bulletType = "1" if ordered else "bullet"
        flowables.append(
            ListFlowable(
                items,
                bulletType=bulletType,
                start=node.get("start") if ordered else None,
                leftIndent=14 + indent_extra,
                bulletFontName=CJK_FONT_NAME or "Helvetica",
            )
        )
        flowables.append(Spacer(1, 4))


def render_table(node, flowables):
    rows = []
    for tr in node.find_all("tr"):
        cells = []
        for cell in tr.find_all(["td", "th"]):
            text = parse_inline(cell)
            style = STYLES["p_noindent"]
            style.fontSize = 10
            style.leading = 15
            cells.append(Paragraph(text, style))
        rows.append(cells)
    if not rows:
        return
    # 等宽列
    n_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < n_cols:
            r.append(Paragraph("", STYLES["p_noindent"]))
    col_w = USABLE_W / n_cols
    tbl = Table(rows, colWidths=[col_w] * n_cols, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("FONTNAME", (0, 0), (-1, -1), CJK_FONT_NAME or "Helvetica"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#a0aec0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    flowables.append(tbl)
    flowables.append(Spacer(1, 6))


def render_code_block(node, flowables):
    code = node.get_text()
    flowables.append(Preformatted(code, STYLES["code"]))


def render_paragraph(node, flowables, base_path: Path):
    """处理 <p> 标签。它可能只包含文本，也可能含 <img>。"""
    # 如果段落里只有图片
    imgs = node.find_all("img")
    text = parse_inline(node).strip()
    if not text and imgs:
        for img in imgs:
            render_image(img, flowables, base_path)
        return
    if not text:
        return
    # 判断是否需要首行缩进：非引用/列表/标题段落才缩进
    style = STYLES["p"]
    # 一些段落是图片说明风格，不缩进
    if any(p in (node.get("class") or []) for p in []):
        style = STYLES["p_noindent"]
    flowables.append(Paragraph(text, style))


def render_heading(node, flowables, level: int):
    text = parse_inline(node).strip()
    if not text:
        return
    style = STYLES.get(f"h{min(level, 4)}", STYLES["h4"])
    flowables.append(Paragraph(text, style))


def render_hr(flowables):
    flowables.append(Spacer(1, 4))
    flowables.append(
        HRFlowable(
            width="60%",
            thickness=0.6,
            color=colors.HexColor("#a0aec0"),
            spaceBefore=4,
            spaceAfter=8,
            hAlign="CENTER",
        )
    )


def render_children(node, flowables, base_path: Path = None, indent_extra: int = 0):
    base_path = base_path or BASE_DIR
    for child in node.children:
        if isinstance(child, NavigableString):
            txt = str(child).strip()
            if not txt:
                continue
            # 裸文本当作段落
            flowables.append(Paragraph(txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), STYLES["p"]))
            continue
        if not isinstance(child, Tag):
            continue
        name = (child.name or "").lower()
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(name[1])
            render_heading(child, flowables, level)
        elif name == "p":
            render_paragraph(child, flowables, base_path)
        elif name == "blockquote":
            render_blockquote(child, flowables, depth=1)
        elif name == "ul":
            render_list(child, flowables, ordered=False, indent_extra=indent_extra)
        elif name == "ol":
            render_list(child, flowables, ordered=True, indent_extra=indent_extra)
        elif name == "table":
            render_table(child, flowables)
        elif name == "pre":
            render_code_block(child, flowables)
        elif name == "hr":
            render_hr(flowables)
        elif name == "div":
            # 处理 <div align="center">…图片</div> 之类
            inner_class = " ".join(child.get("class") or [])
            inner_imgs = child.find_all("img")
            inner_text = child.get_text(strip=True)
            if inner_imgs and not inner_text:
                for img in inner_imgs:
                    render_image(img, flowables, base_path)
            else:
                render_children(child, flowables, base_path, indent_extra)
        elif name == "img":
            render_image(child, flowables, base_path)
        else:
            # 兜底：把内部 inline 文本作为段落
            txt = child.get_text(" ", strip=True)
            if txt:
                flowables.append(
                    Paragraph(
                        txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                        STYLES["p_noindent"],
                    )
                )


# ---------- Markdown → HTML ----------
_MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def preprocess_md_images(md_text: str) -> str:
    """把 markdown 图片语法预先转成 <img>，避免被包在 HTML 块里时不被解析。"""
    return _MD_IMG_RE.sub(r'<img alt="\1" src="\2" />', md_text)


def md_to_html(md_text: str) -> str:
    md_text = preprocess_md_images(md_text)
    md = markdown.Markdown(
        extensions=[
            "extra",   # 表格、代码块、脚注等
            "sane_lists",
            "toc",
        ]
    )
    return md.convert(md_text)


# ---------- 构建单个 PDF ----------
def build_pdf(md_path: Path, pdf_path: Path, title_override: str = None):
    md_text = md_path.read_text(encoding="utf-8")
    html = md_to_html(md_text)
    soup = BeautifulSoup(html, "lxml")

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=title_override or md_path.stem,
        author="高士其（原著） / 21世纪升级版整理",
    )

    flowables = []
    body = soup.body or soup
    render_children(body, flowables, base_path=md_path.parent)
    doc.build(flowables)
    return pdf_path


# ---------- 页眉/页脚 ----------
def draw_page_decorations(canvas, doc):
    canvas.saveState()
    # 页码
    canvas.setFont(CJK_FONT_NAME or "Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#718096"))
    page_text = f"– {doc.page} –"
    canvas.drawCentredString(PAGE_W / 2, 1.2 * cm, page_text)
    # 顶部细线
    canvas.setStrokeColor(colors.HexColor("#cbd5e0"))
    canvas.setLineWidth(0.3)
    canvas.line(LEFT_MARGIN, PAGE_H - 1.3 * cm, PAGE_W - RIGHT_MARGIN, PAGE_H - 1.3 * cm)
    # 左侧书名（小字）
    canvas.setFont(CJK_FONT_NAME or "Helvetica", 8.5)
    canvas.setFillColor(colors.HexColor("#a0aec0"))
    canvas.drawString(LEFT_MARGIN, PAGE_H - 1.0 * cm, "《灰尘的旅行》")
    canvas.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - 1.0 * cm, "高士其")
    canvas.restoreState()


# ---------- 主流程 ----------
def main():
    # 收集文件
    files = []

    # 卷前
    for fname in [
        "灰尘的旅行-总导读.md",
        "灰尘的旅行-目录索引.md",
    ]:
        p = BASE_DIR / fname
        if p.exists():
            files.append((f"卷前·{p.stem}", p))

    # 三部章节
    for part, count in [("第一部", 15), ("第二部", 16), ("第三部", 31)]:
        for i in range(1, count + 1):
            prefix = f"灰尘的旅行-{part}-"
            # 文件名格式：第一部-01-我的名称.md
            candidates = list(BASE_DIR.glob(f"{prefix}{i:02d}-*.md"))
            if not candidates:
                # 兜底：扫描所有匹配
                candidates = [
                    p
                    for p in BASE_DIR.glob(f"{prefix}*.md")
                    if p.stem.split("-")[2] == f"{i:02d}"
                ]
            if candidates:
                p = candidates[0]
                files.append((f"{part}·{p.stem}", p))
            else:
                print(f"警告：未找到 {part} 第 {i:02d} 章")

    # 编后记
    p = BASE_DIR / "灰尘的旅行-编后记.md"
    if p.exists():
        files.append((f"卷末·{p.stem}", p))

    print(f"共找到 {len(files)} 个 Markdown 文件。")

    # 生成各部分 PDF
    generated = []
    for label, md_path in files:
        out_name = f"{md_path.stem}.pdf"
        out_path = CHAPTERS_DIR / out_name
        print(f"生成 {out_name} …")
        try:
            build_pdf(md_path, out_path, title_override=label)
            generated.append((label, out_path))
        except Exception as e:
            print(f"  ✗ 失败：{e}")
            import traceback
            traceback.print_exc()

    # 合并为整本书
    if generated:
        merge_path = OUT_DIR / "灰尘的旅行-完整版.pdf"
        from pypdf import PdfWriter, PdfReader
        writer = PdfWriter()
        for label, p in generated:
            reader = PdfReader(str(p))
            for page in reader.pages:
                writer.add_page(page)
        # 加书签
        page_index = 0
        for label, p in generated:
            reader = PdfReader(str(p))
            n = len(reader.pages)
            # 解析 label 拿到主标题
            title = label.split("·")[-1]
            try:
                writer.add_outline_item(title, page_index)
            except Exception:
                pass
            page_index += n
        with open(merge_path, "wb") as f:
            writer.write(f)
        print(f"\n已生成合并 PDF: {merge_path}")

    print("\n所有文件已输出到:", OUT_DIR)


if __name__ == "__main__":
    main()
