"""The visual half of the no-closed-state rule: nothing on a page says a class is done.

A vocabulary check reads words. It cannot see a green fill, a tick, or a five-of-five
progress bar — and those say "finished" to every reader in the room faster than any sentence
undoes it. So this reads the chips the renderers actually emitted.

Three things fail:

  1. An exposure-class chip carrying a RAG "good" fill. Green is the colour of done, and a
     class with four controls recorded against it is not done: NIST's position is that
     adversarial ML mitigations are empirical rather than guaranteed and that published
     defences have repeatedly been broken by adaptive attacks.
  2. A completion glyph anywhere near a class — a tick, a checkmark entity, "✓", "✔".
  3. A ratio of the shape "3 of 5" or "3/5" in a sentence about classes, which implies a
     target and a shortfall against it. There is no target: a class is not something you
     finish.

Exits 2 if it found no exposure chips at all, because a selector that stopped matching would
otherwise pass in silence — the same anti-vacuity rule the rest of this suite uses.

Usage: _exposurescan.py <page.html>
"""

from __future__ import annotations

import re
import sys

CHIP = re.compile(r'<span class="chip expo" style="background:([^;]+);color:([^"]+)">'
                  r'([^<]*)</span>')
TICK = re.compile(r"✓|✔|&check;|&#10003;|&#x2713;|\bcomplete\b|\bdone\b", re.I)
RATIO = re.compile(r"\b\d+\s*(?:of|/)\s*\d+\b[^.]{0,40}\bclass", re.I)

HEX = re.compile(r"^#([0-9a-fA-F]{6})$")


def is_greenish(colour: str) -> bool:
    """Is this colour read as green by somebody glancing at it?

    Tested by HUE rather than against a list of known good-band hex values, and that is a
    correction rather than a preference. The first version of this scanner held four literal
    fills it believed were "the green one". The library's actual good band is `#E3EDE4`, which
    was not among them — so a planted `G.chip("good")` on an exposure chip passed the guard
    silently, which is the exact failure mode a guard exists to prevent. A palette is a moving
    target and a list of hex values is a snapshot of one moment of it.

    The test is deliberately loose: green is the dominant channel by a visible margin. It
    catches the library's pale `#E3EDE4` and any client brand's green, and it leaves the
    neutral measure fill `#EFEDE7` alone, where red is fractionally dominant.
    """
    match = HEX.match(colour.strip())
    if not match:
        return False
    r, g, b = (int(match.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    return g > r + 3 and g > b + 3


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    html = open(argv[1], encoding="utf-8").read()
    chips = CHIP.findall(html)
    # The two surfaces say this differently, on purpose. The operational view emits a chip per
    # class, because an operator is scanning. The board view writes the same fact as a
    # sentence, because a board reads. Both must be inspectable, so the anti-vacuity gate
    # accepts either — and fails when a page carries NEITHER, which is what a selector that
    # stopped matching, or a section quietly dropped, would look like.
    named = len(re.findall(r"NISTAML\.\d\d", html))
    if not chips and not named:
        print("no exposure-class chips AND no NISTAML class named in %s — either the selector "
              "stopped matching or the page stopped saying what anything is exposed to, and "
              "this guard proved nothing" % argv[1], file=sys.stderr)
        return 2
    problems = []
    for fill, fg, label in chips:
        fill = fill.strip()
        if is_greenish(fill) or is_greenish(fg.strip()):
            problems.append("a class chip renders green (%s on %s, %r) — green is the colour "
                            "of done, and an attack class is never done" % (fg, fill, label))
        if TICK.search(label):
            problems.append("a class chip reads %r, which says finished" % label)
    text = re.sub(r"<[^>]+>", " ", html)
    for match in RATIO.finditer(text):
        problems.append("a completion ratio about classes: %r" % match.group(0).strip())
    if TICK.search(text) and "attack class" in text.lower():
        # Narrow deliberately: a tick anywhere on a page that also talks about attack classes
        # is worth a human look, and this page has no legitimate reason to carry one.
        problems.append("a completion glyph or the word 'complete'/'done' on a page about "
                        "attack classes")
    print("inspected %d exposure chip(s) and %d named class(es)"
          % (len(chips), named), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
