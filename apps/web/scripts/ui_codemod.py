"""Mechanical pass toward docs/UI_STANDARDS.md: hex classes -> tokens, tiny text -> 12px,
heavy weights -> semibold, radius/shadow -> card/tile tokens. Class names only; no logic.

    python scripts/ui_codemod.py src/app/college [more paths...]   # rewrites in place
    python scripts/ui_codemod.py --check src                       # CI: fails if anything is off the standard

Dark code/lab surfaces (#1B2236, #141A29, #0F172A ...) are left alone on purpose (DARK_OK).
"""
import re
import sys
from pathlib import Path

HEX = {
    # text
    "0F1F3A": "ink", "0F172A": None, "334155": "ink-soft", "475569": "ink-soft",
    "64748B": "muted", "94A3B8": "subtle",
    # surfaces and lines
    "FFFFFF": "surface", "F8FAFC": "surface-2", "F1F5F9": "line-soft", "E2E8F0": "line", "CBD5E1": "line-strong",
    # brand
    "14284B": "navy", "1E3A6E": "navy-2", "3B76EC": "side", "1A3A8C": "side-2", "2B5CD0": "brand", "1E46B0": "brand-hover", "204497": "brand-hover",
    "2049AA": "brand-hover", "EFF6FF": "brand-soft", "BFDBFE": "brand-line",
    "2BB3A0": "teal", "249B8A": "teal-hover", "239988": "teal-hover",
    # success
    "166534": "success", "15803D": "success", "065F46": "success", "059669": "success",
    "10B981": "success-fill", "DCFCE7": "success-soft", "F0FDF4": "success-faint", "ECFDF5": "success-faint",
    "BBF7D0": "success-line", "86EFAC": "success-line", "A7F3D0": "success-line",
    # warning
    "B45309": "warning", "92400E": "warning", "9A3412": "warning", "7C2D12": "warning", "D97706": "warning",
    "F59E0B": "warning-fill", "FBBF24": "warning-fill", "FEF3C7": "warning-soft", "FFFBEB": "warning-faint",
    "FFF7ED": "warning-faint", "FDE68A": "warning-line", "FED7AA": "warning-line",
    # danger
    "DC2626": "danger", "D93636": "danger", "B91C1C": "danger", "991B1B": "danger", "881337": "danger",
    "F87171": "danger-fill", "FEE2E2": "danger-soft", "FDE8E8": "danger-soft", "FEF2F2": "danger-faint",
    "FFF5F5": "danger-faint", "FECACA": "danger-line", "FCA5A5": "danger-line",
    # info / violet
    "1D4ED8": "info", "1E40AF": "info", "1E3A8A": "info", "DBEAFE": "info-soft",
    "7C5CE0": "violet", "6D28D9": "violet", "4338CA": "violet", "3730A3": "violet", "5B5FC7": "violet",
    "EDE9FE": "violet-soft", "F5F3FF": "violet-soft", "EEF2FF": "violet-soft", "DDD6FE": "violet-soft",
}

RULES = [
    # arbitrary hex in a class: bg-[#2B5CD0]/30 -> bg-brand/30
    (re.compile(r"(?<=-)\[#([0-9A-Fa-f]{6})\]"), lambda m: HEX.get(m.group(1).upper()) or m.group(0)),
    # tiny text -> 12px caption
    (re.compile(r"\btext-\[(?:8|9|10|11)px\]"), lambda m: "text-caption"),
    # weights: regular / medium / semibold only
    (re.compile(r"\bfont-(?:black|extrabold|bold)\b"), lambda m: "font-semibold"),
    # shape
    (re.compile(r"\brounded-(?:2xl|3xl|xl)\b"), lambda m: "rounded-card"),
    (re.compile(r"\brounded-(?:lg|md)\b"), lambda m: "rounded-tile"),
    (re.compile(r"\bshadow-(?:md|lg|xl|2xl)\b"), lambda m: "shadow-pop"),
    (re.compile(r"\bshadow-(?:xs|sm)\b"), lambda m: "shadow-card"),
    (re.compile(r"(?<=[\s\"'`])shadow(?=[\s\"'`])"), lambda m: "shadow-card"),
    # shouting labels -> sentence case (text is unchanged; only CSS)
    (re.compile(r"\s?\buppercase\b"), lambda m: ""),
    (re.compile(r"\s?\btracking-(?:wide|wider|widest)\b"), lambda m: ""),
]


# A help line that opens the page becomes the shell's subtitle (one style, right under the h1):
#   <AppShell pageTitle={t("x.title")}>\n <div ...>\n <p className="text-xs text-muted">{t("x.help")}</p>
SUBTITLE = re.compile(
    r'(<AppShell pageTitle=\{[^}]+\})(>\s*\n\s*<div[^\n>]*>\s*\n)'
    r'[ \t]*<p className="(?:text-(?:xs|sm|caption|\[11px\]))? ?text-(?:muted|\[#64748B\])(?: [^"]*)?">((?:(?!</p>).)+)</p>[ \t]*\r?\n',
)


def _subtitle(m: re.Match) -> str:
    body = m.group(3).strip()
    value = body if re.fullmatch(r"\{[^{}]*\}", body) else "{<>" + body + "</>}"
    return f"{m.group(1)} pageSubtitle={value}{m.group(2)}"


# Page sections are 24px apart: the wrapper right inside AppShell gets space-y-6.
PAGE_GAP = re.compile(r'(<AppShell[^\n]*>\s*\r?\n\s*<div className="[^"]*?)\bspace-y-[2-5]\b')


def rewrite(text: str) -> str:
    text = SUBTITLE.sub(_subtitle, text, count=1)
    text = PAGE_GAP.sub(r"\1space-y-6", text)  # every AppShell (loading / error / main states)
    for rx, fn in RULES:
        text = rx.sub(fn, text)
    # a removal at the very start of a class string leaves a leading space
    return re.sub(r'(className=")\s+', r"\1", text)


# Dark code/lab surfaces may stay as literal classes; any other hex in a class needs a token.
DARK_OK = {"0F172A", "1E293B", "2D3748", "1B2236", "141A29", "0B0F19", "1E6B7B", "93C5FD", "38BDF8"}
UNKNOWN_HEX = re.compile(r"-\[#([0-9A-Fa-f]{6})\]")


def main(argv: list[str]) -> int:
    check = "--check" in argv
    paths = [Path(a) for a in argv if a != "--check"]
    changed = 0
    problems = 0
    for root in paths:
        files = [root] if root.is_file() else sorted(root.rglob("*.tsx"))
        for f in files:
            if "components/ui" in f.as_posix():
                continue
            with open(f, encoding="utf-8", newline="") as fh:  # keep line endings as they are
                old = fh.read()
            new = rewrite(old)
            if new != old:
                changed += 1
                print(("would change " if check else "changed ") + f.as_posix())
                if not check:
                    with open(f, "w", encoding="utf-8", newline="") as fh:
                        fh.write(new)
            for n, line in enumerate(new.splitlines(), 1):
                for m in UNKNOWN_HEX.finditer(line):
                    if m.group(1).upper() not in DARK_OK:
                        problems += 1
                        print(f"{f.as_posix()}:{n}: colour #{m.group(1)} has no token; add one to globals.css @theme")
    print(f"{changed} file(s) off the standard, {problems} colour(s) without a token")
    if check and (changed or problems):
        print("Fix with: python scripts/ui_codemod.py <path>   (rules: docs/UI_STANDARDS.md)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
