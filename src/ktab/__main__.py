"""python -m ktab check|tree|fmt|tex song.ktab"""
import argparse
import os
import sys

from antlr4.tree.Tree import TerminalNode

from . import KtabError, parse_file, parse_tree
from ._gen.KalimbaLexer import KalimbaLexer

# playable range per kalimba size as (lowest, highest) scale index, 0 = "1"; C tuning
RANGES = {17: (0, 16), 21: (-3, 16), 8: (0, 7)}


def cmd_check(path, tines):
    song = parse_file(path)
    lo, hi = RANGES.get(tines, (None, None))
    for k, v in song.headers.items():
        print(f"@{k}: {v}")
    warnings = 0
    for si, st in enumerate(song.stanzas, 1):
        print(f"stanza {si}  ({len(st.lines)} line{'s' if len(st.lines) > 1 else ''})")
        for ln in st.lines:
            words = ln.words
            n_syl = sum(len(w.syllables) for w in words)
            n_notes = sum(1 for _ in ln.notes())
            text = " ".join("-".join(s.text for s in w.syllables) for w in words)
            print(f"  {ln.pos[0]:3}  {len(words):2} words {n_syl:2} syll {n_notes:2} notes "
                  f"{str(ln.beats):>5} beats  {text}")
    for n in song.notes():
        if lo is not None and not n.is_rest and not lo <= n.scale_index <= hi:
            print(f"warning: line {n.pos[0]}:{n.pos[1]}: {n} is outside a {tines}-key kalimba")
            warnings += 1
    print(f"OK: {len(song.stanzas)} stanza(s), {len(song.lines)} lines, {warnings} warning(s)")


def cmd_tree(path):
    with open(path, encoding="utf-8-sig") as f:
        tree, parser = parse_tree(f.read())

    def walk(node, depth):
        if isinstance(node, TerminalNode):
            t = node.getSymbol()
            name = KalimbaLexer.symbolicNames[t.type] if t.type > 0 else "EOF"
            print("  " * depth + (f"{name} {t.text!r}" if t.type > 0 else "EOF"))
            return
        name = parser.ruleNames[node.getRuleIndex()]
        shown = f"  «{node.getText()}»" if name in ("word", "syllable", "note", "hold") else ""
        print("  " * depth + name + shown)
        for ch in node.getChildren():
            walk(ch, depth + 1)

    walk(tree, 0)


def main():
    ap = argparse.ArgumentParser(prog="python -m ktab", description="Kalimba tab tools")
    ap.add_argument("command", choices=["check", "tree", "fmt", "tex"],
                    help="check: syntax + beats per line; tree: parse tree; "
                         "fmt: canonical form; tex: printable sheet (.tex and .pdf)")
    ap.add_argument("file")
    ap.add_argument("--tines", type=int, default=17, help="kalimba size for range warnings")
    ap.add_argument("-o", "--out", help="tex: output .tex path (default: next to the input)")
    ap.add_argument("--no-pdf", action="store_true", help="tex: only write the .tex file")
    a = ap.parse_args()
    try:
        if a.command == "tex":
            from .latex import LatexError, write
            stem = os.path.splitext(a.file)[0]
            title = os.path.basename(stem).replace("_", " ").title()
            try:
                for note in write(parse_file(a.file), a.out or stem + ".tex", title, pdf=not a.no_pdf):
                    print(note)
            except LatexError as e:
                sys.exit(f"{a.file}: {e}")
        elif a.command == "check":
            cmd_check(a.file, a.tines)
        elif a.command == "tree":
            cmd_tree(a.file)
        else:
            sys.stdout.write(str(parse_file(a.file)))
    except KtabError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
