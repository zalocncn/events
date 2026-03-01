#!/usr/bin/env python3
"""Update blog post HTML files to match home page visual identity: nav, colors, fonts."""
import re
from pathlib import Path

BLOG_DIR = Path(__file__).resolve().parent.parent / "lime-seo-implementation" / "blog"

NAV_REPLACEMENT = """    <header class="w-full h-14 px-4 md:px-6 flex items-center justify-between border-b border-white/5 bg-[#1A1A1D] sticky top-0 z-50">
        <a href="../../blog.html" class="text-[#A0A0A0] hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-[#6F42C1]/45 rounded-sm flex items-center gap-2" aria-label="Volver al blog">
            <i data-lucide="arrow-left" class="w-5 h-5" stroke-width="1.5"></i>
            <span class="text-sm font-medium hidden sm:inline">Blog</span>
        </a>
        <a href="../../index.html" class="flex items-center gap-2">
            <div class="w-6 h-6 rounded-full bg-gradient-to-tr from-[#FFC107] to-[#6F42C1] flex items-center justify-center">
                <i data-lucide="sun" class="w-3.5 h-3.5 text-white" stroke-width="2"></i>
            </div>
            <span class="text-base font-semibold tracking-tight text-white">Lima</span>
        </a>
        <div class="w-5 h-5"></div>
    </header>"""

FOOTER_REPLACEMENT = """    <footer class="w-full border-t border-white/5 mt-12 py-6">
        <div class="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex justify-center">
            <a href="../../index.html" class="text-sm text-[#A0A0A0] hover:text-[#8B5CF6] transition-colors flex items-center gap-1.5">
                <i data-lucide="calendar-days" class="w-4 h-4" stroke-width="1.5"></i>
                Volver al calendario
            </a>
        </div>
    </footer>
    <script>if (typeof lucide !== 'undefined') lucide.createIcons();</script>"""

# V3: nav and footer use ../../../ (blog is in lime-seo-v3/blog/)
NAV_V3 = """    <header class="w-full h-14 px-4 md:px-6 flex items-center justify-between border-b border-white/5 bg-[#1A1A1D] sticky top-0 z-50">
        <a href="../../../blog.html" class="text-[#A0A0A0] hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-[#6F42C1]/45 rounded-sm flex items-center gap-2" aria-label="Volver al blog">
            <i data-lucide="arrow-left" class="w-5 h-5" stroke-width="1.5"></i>
            <span class="text-sm font-medium hidden sm:inline">Blog</span>
        </a>
        <a href="../../../index.html" class="flex items-center gap-2">
            <div class="w-6 h-6 rounded-full bg-gradient-to-tr from-[#FFC107] to-[#6F42C1] flex items-center justify-center">
                <i data-lucide="sun" class="w-3.5 h-3.5 text-white" stroke-width="2"></i>
            </div>
            <span class="text-base font-semibold tracking-tight text-white">Lima</span>
        </a>
        <div class="w-5 h-5"></div>
    </header>"""

FOOTER_V3 = """    <footer class="w-full border-t border-white/5 mt-12 py-6">
        <div class="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex justify-center">
            <a href="../../../index.html" class="text-sm text-[#A0A0A0] hover:text-[#8B5CF6] transition-colors flex items-center gap-1.5">
                <i data-lucide="calendar-days" class="w-4 h-4" stroke-width="1.5"></i>
                Volver al calendario
            </a>
        </div>
    </footer>
    <script>if (typeof lucide !== 'undefined') lucide.createIcons();</script>"""

FULL_STYLE = """    <style>
        html{scroll-behavior:smooth;}
        body { font-family: 'Inter', -apple-system, sans-serif; background-color: #1A1A1D; color: #FFFFFF; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1A1A1D; }
        ::-webkit-scrollbar-thumb { background: #2E2E32; border-radius: 4px; }
        .selection\\:bg-\\[\\#6F42C1\\]::selection { background-color: #6F42C1; color: white; }
    </style>"""


def update_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    # 1. html tag
    text = text.replace('<html lang="es">', '<html lang="es" class="dark">', 1)

    # 2. Head: add Lucide if missing
    if "unpkg.com/lucide" not in text:
        text = text.replace(
            '<script src="https://cdn.tailwindcss.com"></script>\n',
            '<script src="https://cdn.tailwindcss.com"></script>\n    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>\n',
            1,
        )
    # Replace old minimal style with full one
    old_style = """    <style>
        html{scroll-behavior:smooth;}
        body{font-family:'Inter',sans-serif;}
    </style>"""
    new_style = FULL_STYLE
    if old_style in text:
        text = text.replace(old_style, new_style, 1)

    # 3. Body class
    text = text.replace(
        '<body class="bg-gray-950 text-gray-100">',
        '<body class="min-h-screen flex flex-col antialiased selection:bg-[#6F42C1] selection:text-white pb-12">',
        1,
    )

    # 4. Nav block: with comment (original) OR old full-site nav (🍊 Lima, Calendario, Blog, Distritos, Acerca de)
    nav_pat = r'    <!-- Navigation -->\s*\n\s*<nav[^>]*>[\s\S]*?</nav>'
    if re.search(nav_pat, text):
        text = re.sub(nav_pat, NAV_REPLACEMENT, text, count=1)
    else:
        nav_pat2 = r'    <nav class="fixed w-full z-50[^>]*>[\s\S]*?</nav>'
        if re.search(nav_pat2, text):
            text = re.sub(nav_pat2, NAV_REPLACEMENT, text, count=1)

    # 5. Article header: with or without <!-- Header --> comment
    text = re.sub(
        r'    <!-- Header -->\s*\n\s*<header class="pt-28 pb-12 bg-gradient-to-b from-gray-900 to-gray-950">',
        '    <!-- Header -->\n    <header class="pt-10 pb-10 sm:pt-14 sm:pb-12">',
        text,
        count=1,
    )
    text = re.sub(
        r'    <header class="pt-28 pb-12 bg-gradient-to-b from-gray-900 to-gray-950">',
        '    <!-- Header -->\n    <header class="pt-10 pb-10 sm:pt-14 sm:pb-12">',
        text,
        count=1,
    )
    text = re.sub(
        r'rounded-full bg-orange-500/10 border border-orange-500/20',
        'rounded-full bg-[#6F42C1]/10 border border-[#6F42C1]/20',
        text,
    )
    text = re.sub(r'text-orange-400', 'text-[#B794F4]', text)
    text = re.sub(r'text-orange-300', 'text-[#B794F4]', text)
    text = re.sub(r'hover:text-orange-300', 'hover:text-[#B794F4]', text)
    text = re.sub(r'text-gray-400 mb-6', 'text-[#A0A0A0] mb-6', text, count=1)
    text = re.sub(r'text-sm text-gray-500', 'text-sm text-[#888]', text)

    # 6. Article content wrapper
    text = text.replace(
        'bg-gray-900 rounded-2xl p-8 md:p-12 border border-gray-800',
        'bg-[#242428] rounded-2xl p-8 md:p-12 border border-white/10',
    )

    # 7. Global color replacements
    text = re.sub(r'\bbg-gray-900\b', 'bg-[#242428]', text)
    text = re.sub(r'\bborder-gray-800\b', 'border-white/10', text)
    text = re.sub(r'\bborder-gray-700\b', 'border-white/10', text)
    text = re.sub(r'\btext-gray-300\b', 'text-[#C0C0C0]', text)
    text = re.sub(r'\btext-gray-400\b', 'text-[#A0A0A0]', text)
    text = re.sub(r'\btext-gray-500\b', 'text-[#888]', text)
    text = re.sub(r'\btext-gray-600\b', 'text-[#666]', text)
    text = re.sub(r'\bbg-orange-500/10\b', 'bg-[#6F42C1]/10', text)
    text = re.sub(r'\bborder-orange-500/20\b', 'border-[#6F42C1]/20', text)
    text = re.sub(r'\bbg-gray-800/50\b', 'bg-white/[0.06]', text)
    text = re.sub(r'\bhover:bg-gray-800\b', 'hover:bg-white/[0.08]', text)
    text = re.sub(r'\bfrom-orange-600 to-orange-500\b', 'from-[#6F42C1] to-[#8B5CF6]', text)
    text = re.sub(r'\btext-orange-100\b', 'text-white/90', text)
    text = re.sub(r'bg-gray-900 hover:bg-gray-800', 'bg-[#1A1A1D] hover:bg-[#242428]', text)

    # 7b. Lime/emerald → purple (visual identity)
    text = re.sub(r'\bbg-lime-500/10\b', 'bg-[#6F42C1]/10', text)
    text = re.sub(r'\bborder-lime-500/30\b', 'border-[#6F42C1]/20', text)
    text = re.sub(r'\bborder-lime-500/20\b', 'border-[#6F42C1]/20', text)
    text = re.sub(r'\btext-lime-400\b', 'text-[#B794F4]', text)
    text = re.sub(r'\btext-lime-300\b', 'text-[#B794F4]', text)
    text = re.sub(r'\bhover:text-lime-300\b', 'hover:text-[#B794F4]', text)
    text = re.sub(r'\btext-lime-100\b', 'text-white/90', text)
    text = re.sub(r'\bfrom-lime-600 to-emerald-600\b', 'from-[#6F42C1] to-[#8B5CF6]', text)
    text = re.sub(r'\bbg-gradient-to-r from-lime-600 to-emerald-600\b', 'bg-gradient-to-r from-[#6F42C1] to-[#8B5CF6]', text)
    text = re.sub(r'\bhover:border-lime-500/50\b', 'hover:border-[#6F42C1]/50', text)
    # Calendar/home links: point to same-site calendar
    text = re.sub(r'href="https://limaeventos\.app"[^>]*>', 'href="../../index.html">', text)

    # Ensure full style block if still minimal (e.g. only body + scroll, no scrollbar)
    if "scrollbar-track" not in text and "<style>" in text:
        text = re.sub(
            r'    <style>\s*\n\s*body\s*\{[^}]+\}\s*\n\s*</style>',
            FULL_STYLE,
            text,
            count=1,
        )
        # Variant: html + body on separate lines
        text = re.sub(
            r'    <style>\s*\n\s*html\s*\{[^}]+\}\s*\n\s*body\s*\{[^}]+\}\s*\n\s*</style>',
            FULL_STYLE,
            text,
            count=1,
        )
        # Single-line style: html{...}body{...}
        text = re.sub(
            r'    <style>html\{scroll-behavior:smooth;\}body\{font-family:[^}]+\}</style>',
            FULL_STYLE,
            text,
            count=1,
        )

    # 8a. Fix internal links: from blog folder, calendar is ../../index.html, blog list is ../../blog.html
    text = text.replace('href="../index.html"', 'href="../../index.html"')
    text = text.replace('href="index.html"', 'href="../../blog.html"')
    # Districts/about may not exist at ../../ ; point to calendar instead
    text = re.sub(r'href="\.\./districts/[^"]*"', 'href="../../index.html"', text)
    text = re.sub(r'href="\.\./about\.html"', 'href="../../index.html"', text)
    text = re.sub(r'href="\.\./advertise\.html"', 'href="../../index.html"', text)

    # 8. Footer: replace any old multi-link footer with simple "Volver al calendario"
    if 'Volver al calendario' not in text:
        # With comment
        footer_pat = r'    <!-- Footer -->\s*\n\s*<footer[^>]*>[\s\S]*?</footer>'
        if re.search(footer_pat, text):
            text = re.sub(footer_pat, FOOTER_REPLACEMENT, text, count=1)
        else:
            # Without comment (some posts)
            footer_pat2 = r'    <footer class="bg-\[#242428\][^>]*>[\s\S]*?</footer>'
            if re.search(footer_pat2, text):
                text = re.sub(footer_pat2, FOOTER_REPLACEMENT, text, count=1)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def update_file_v3(path: Path) -> bool:
    """Apply post-01 visual identity to v3 posts (lime-seo-v3/blog/). Paths use ../../../."""
    text = path.read_text(encoding="utf-8")
    original = text

    # 1. Style: full block if missing scroll/selection
    if "scroll-behavior" not in text or "scrollbar-track" not in text:
        text = re.sub(r'    <style>\s*\n[\s\S]*?</style>', FULL_STYLE, text, count=1)
    # 2. Body: add pb-12
    text = re.sub(
        r'<body class="min-h-screen flex flex-col antialiased selection:bg-\[#6F42C1\] selection:text-white">',
        '<body class="min-h-screen flex flex-col antialiased selection:bg-[#6F42C1] selection:text-white pb-12">',
        text,
        count=1,
    )
    # 3. Nav: replace with NAV_V3
    old_nav = r'    <header class="w-full h-14 px-4 md:px-6 flex items-center justify-between border-b border-white/5 bg-\[#1A1A1D\] sticky top-0 z-50">\s*\n\s*<a href="\.\./\.\./blog\.html"[^>]*>[\s\S]*?</header>'
    if re.search(old_nav, text):
        text = re.sub(old_nav, NAV_V3, text, count=1)
    # 4. Fix ../../ to ../../../ for v3 depth
    text = text.replace('href="../../blog.html"', 'href="../../../blog.html"')
    text = text.replace('href="../../index.html"', 'href="../../../index.html"')
    # 5. Remove <main ...> wrapper
    text = re.sub(
        r'    <main class="flex-1 w-full max-w-\[800px\] mx-auto px-4 sm:px-6 lg:px-8 pt-10 sm:pt-14 pb-16">\s*\n\s*\n\s*',
        '',
        text,
        count=1,
    )
    # 6. Restructure: article header -> post-01 style hero; prose-custom -> article with card wrapper
    # Allow optional leading newline/whitespace after main removal
    text = re.sub(
        r'\s*        <article>\s*\n            <header class="mb-10">',
        '    <!-- Header -->\n    <header class="pt-10 pb-10 sm:pt-14 sm:pb-12">\n        <div class="max-w-4xl mx-auto px-6">\n            <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#6F42C1]/10 border border-[#6F42C1]/20 mb-6">\n                ',
        text,
        count=1,
    )
    text = re.sub(
        r'(<span class="text-\[#B794F4\] text-xs font-medium uppercase tracking-wider">[^<]+</span>)\s*\n\s*<h1',
        r'\1\n            </div>\n            <h1',
        text,
        count=1,
    )
    text = re.sub(
        r'                </div>\s*\n            </header>\s*\n            <div class="prose-custom">',
        '                </div>\n        </div>\n    </header>\n\n    <!-- Article -->\n    <article class="py-12">\n        <div class="max-w-4xl mx-auto px-6">\n            <div class="bg-[#242428] rounded-2xl p-8 md:p-12 border border-white/10">\n                ',
        text,
        count=1,
    )
    # 7. Close article card and main; replace old footer with FOOTER_V3
    text = re.sub(
        r'            </div>\s*\n        </article>\s*\n    </main>\s*\n\s*\n    <footer class="w-full border-t border-white/5 py-8 text-center">[\s\S]*?</footer>',
        '            </div>\n        </div>\n    </article>\n\n' + FOOTER_V3,
        text,
        count=1,
    )
    # 8. Lime/emerald and link fixes
    text = re.sub(r'\bbg-lime-500/10\b', 'bg-[#6F42C1]/10', text)
    text = re.sub(r'\bborder-lime-500/30\b', 'border-[#6F42C1]/20', text)
    text = re.sub(r'\btext-lime-400\b', 'text-[#B794F4]', text)
    text = re.sub(r'\btext-lime-300\b', 'text-[#B794F4]', text)
    text = re.sub(r'\bfrom-lime-600 to-emerald-600\b', 'from-[#6F42C1] to-[#8B5CF6]', text)
    text = re.sub(r'href="https://limaeventos\.app"[^>]*>', 'href="../../../index.html">', text)
    text = re.sub(r'text-sm text-\[#666\]', 'text-sm text-[#888]', text)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    updated = 0
    if not BLOG_DIR.exists():
        print("Blog dir not found")
        return
    for f in sorted(BLOG_DIR.glob("post-*.html")):
        if update_file(f):
            updated += 1
            print(f"  Updated {f.name}")
    v3_dir = BLOG_DIR / "lime-seo-v3" / "blog"
    if v3_dir.exists():
        for f in sorted(v3_dir.glob("post-*.html")):
            if update_file_v3(f):
                updated += 1
                print(f"  Updated v3 {f.name}")
    print(f"Done. Updated {updated} files.")


if __name__ == "__main__":
    main()
