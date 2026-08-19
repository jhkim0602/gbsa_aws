#!/usr/bin/env python3
"""Mechanical fidelity checks for the Tailwind conversion.

Catches the defects that are easy to introduce and hard to see:
  1. a named `text-*` utility, which injects a line-height the source never declared
  2. a leftover project class name in a `className`
  3. a token that looks like a utility but compiles to nothing (`bg-link`, `text-text`)
  4. a `@media (max-width:)` breakpoint with no surviving `mw-N:` counterpart
  5. a built-in `max-[Npx]:`, which is an EXCLUSIVE `width < Npx` query — the source
     stylesheets use inclusive `max-width: Npx`, so use the `mw-N:` variant instead

Run from the repo root. Exits non-zero when a hard defect is found.

Files converted on the renewal branch use `text-sm`/`slate-*` on purpose — that was a
redesign, not a port — so they are exempt from check 1. See EXEMPT below.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Named size utilities carry a paired line-height in Tailwind v4; this design declares 480
# font-sizes against 83 line-heights, so a named size silently changes leading.
NAMED_TEXT_SIZES = (
    "xs",
    "sm",
    "base",
    "lg",
    "xl",
    "2xl",
    "3xl",
    "4xl",
    "5xl",
    "6xl",
    "7xl",
    "8xl",
    "9xl",
)

# Written fresh on `feature/uiux-renewal` rather than ported, so their typography is a
# deliberate choice. Anything not listed here is a conversion and must keep the source's
# leading. `ApplicantDetail.tsx` is partly each: only its new submissions list is exempt,
# which the line range pins down.
EXEMPT: tuple[tuple[str, range | None], ...] = (
    ("features/interview/InterviewRoom.tsx", None),
    ("features/interview/Avatar.tsx", None),
    ("features/submissions/index.tsx", None),
    ("features/hiring/tech-stack-combobox/", None),
    ("features/hiring/role-selector/", None),
    ("features/hiring/steps/InterviewDesigner.tsx", None),
    ("features/hiring/steps/EvaluationDesigner.tsx", None),
    ("features/hiring/steps/ApplicantMaterials.tsx", None),
    ("features/hiring/components/HiringAiFlow.tsx", None),
    ("features/company/ApplicantDetail.tsx", range(595, 660)),
)


def is_exempt(rel: str, line: int) -> bool:
    return any(frag in rel and (lines is None or line in lines) for frag, lines in EXEMPT)


# `:root` aliases in design-system/theme.css, not `@theme` keys — these compile to nothing.
# Verified by compiling a probe against theme.css.
NON_UTILITIES = (
    "text-text",
    "text-text-secondary",
    "text-link",
    "text-link-strong",
    "text-purple",
    "bg-text",
    "bg-link",
    "bg-link-strong",
    "bg-purple",
    "bg-purple-soft",
    "bg-product-bar",
    "border-link",
    "border-link-strong",
    "border-text",
)


def tsx_files() -> list[pathlib.Path]:
    return sorted(
        p
        for p in (ROOT / "apps").rglob("*.tsx")
        if "node_modules" not in p.parts and "dist" not in p.parts and "__tests__" not in p.parts
    )


def css_files() -> list[pathlib.Path]:
    return sorted(
        p
        for p in (ROOT / "apps").rglob("*.css")
        if "node_modules" not in p.parts and "dist" not in p.parts
    )


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def class_attrs(src: str) -> list[tuple[int, str]]:
    """Every className value with its 1-indexed line number."""
    out = []
    for m in re.finditer(r'className=(?:"([^"]*)"|\{`([^`]*)`\})', src, re.S):
        value = m.group(1) or m.group(2) or ""
        out.append((src[: m.start()].count("\n") + 1, value))
    return out


def tokens(value: str) -> list[str]:
    """Literal class tokens; `${...}` interpolations are not checkable."""
    return re.sub(r"\$\{[^}]*\}", " ", value).split()


def check_named_text_sizes() -> list[str]:
    problems = []
    named = set(NAMED_TEXT_SIZES)
    for path in tsx_files():
        rel = str(path.relative_to(ROOT))
        for line, value in class_attrs(path.read_text()):
            if is_exempt(rel, line):
                continue
            for token in tokens(value):
                bare = token.split(":")[-1]
                if bare.startswith("text-") and bare[5:] in named:
                    problems.append(
                        f"{rel}:{line}: {bare} injects a line-height; "
                        f"use an arbitrary size like text-[14px]"
                    )
    return problems


def check_non_utilities() -> list[str]:
    problems = []
    for path in tsx_files():
        for line, value in class_attrs(path.read_text()):
            for token in tokens(value):
                if token.split(":")[-1] in NON_UTILITIES:
                    problems.append(
                        f"{path.relative_to(ROOT)}:{line}: '{token}' is a :root alias, "
                        f"not a @theme key — it compiles to nothing"
                    )
    return problems


def project_class_names() -> set[str]:
    """Class names the app stylesheets still define."""
    names: set[str] = set()
    for path in css_files():
        names |= set(re.findall(r"\.(-?[a-zA-Z_][a-zA-Z0-9_-]*)", strip_comments(path.read_text())))
    # Provided by design-system/theme.css, or surviving on purpose.
    return names - {"sr-only", "skip-link"}


def check_leftover_classes() -> list[str]:
    defined = project_class_names()
    problems = []
    for path in tsx_files():
        for line, value in class_attrs(path.read_text()):
            for token in tokens(value):
                if token in defined:
                    problems.append(
                        f"{path.relative_to(ROOT)}:{line}: still references project class '{token}'"
                    )
    return problems


def check_exclusive_breakpoints() -> list[str]:
    """`max-[Npx]:` compiles to `@media (width < Npx)` — one pixel narrower than the source.

    Verified against tailwindcss@4.3.3. Several breakpoints here are real device widths
    (360/400/480/600/720), so the off-by-one is visible. `mw-N:` variants in
    design-system/theme.css emit the inclusive query the stylesheets declare.
    """
    problems = []
    for path in tsx_files():
        src = path.read_text()
        for m in re.finditer(r"max-\[(\d+)px\]:", src):
            problems.append(
                f"{path.relative_to(ROOT)}:{src[: m.start()].count(chr(10)) + 1}: "
                f"'{m.group(0)}' is exclusive (width < {m.group(1)}px); "
                f"use 'mw-{m.group(1)}:' for the inclusive max-width the source declares"
            )
    return problems


def check_variant_order() -> list[str]:
    """`@custom-variant` blocks emit in declaration order, so that order is the cascade.

    Tailwind sorts its built-in `max-*` variants descending; ours it does not touch. The
    stylesheets are desktop-first, so at 600px — where both `mw-780:` and `mw-620:` match —
    the narrower query has to be emitted last to win. Declaring these ascending silently
    inverts every pair of breakpoints that set the same property.
    """
    theme = ROOT / "packages" / "design-system" / "theme.css"
    widths = [int(w) for w in re.findall(r"@custom-variant mw-(\d+) ", theme.read_text())]
    return [
        f"design-system/theme.css: mw-{widths[i]} is declared before mw-{widths[i + 1]}; "
        f"@custom-variant order is cascade order, so these must run widest-first"
        for i in range(len(widths) - 1)
        if widths[i] < widths[i + 1]
    ]


def check_breakpoints() -> list[str]:
    """A max-width breakpoint must survive either as CSS or as a max-[Npx]: variant."""
    declared: set[str] = set()
    for path in css_files():
        declared |= set(re.findall(r"max-width:\s*(\d+)px", strip_comments(path.read_text())))

    used = set(declared)  # still in CSS, so still applied
    for path in tsx_files():
        used |= set(re.findall(r"\bmw-(\d+):", path.read_text()))

    return [
        f"breakpoint max-width:{bp}px has no mw-{bp}: counterpart and no surviving media query"
        for bp in sorted(declared - used, key=int)
    ]


def main() -> int:
    hard = (
        check_named_text_sizes()
        + check_non_utilities()
        + check_leftover_classes()
        + check_exclusive_breakpoints()
        + check_variant_order()
    )
    soft = check_breakpoints()

    for label, items in (("DEFECT", hard), ("REVIEW", soft)):
        for item in items:
            print(f"{label}: {item}")

    print(
        f"\n{len(hard)} defect(s), {len(soft)} item(s) to review across {len(tsx_files())} files."
    )
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
