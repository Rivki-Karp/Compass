"""Text normalization applied to both queries and candidates before fuzzy matching."""

import re
import unicodedata

_FINAL_LETTERS = str.maketrans("ךםןףץ", "כמנפצ")
# Hebrew points and cantillation marks (niqqud), U+0591..U+05C7, minus the punctuation signs in
# that block (maqaf U+05BE, paseq U+05C0, sof pasuq U+05C3, nun hafukha U+05C6).
_NIQQUD = re.compile(r"[֑-ׇֽֿׁׂׅׄ]")
# Gender forms: מפתח/ת, אנליסט/ית, מנהל/ה -> the base form.
_GENDER_SUFFIX = re.compile(r"/(?:ית|ת|ה)(?=\s|$)")
# Apostrophe, backtick, right single quote, double quote, geresh (U+05F3) and gershayim (U+05F4)
# are part of a word (ג'י, ספורטז׳, סה״כ): drop them. Any other punctuation separates words.
_IN_WORD = re.compile(r"['`’\"׳״]")
_PUNCTUATION = re.compile(r"[^\w\s]|_")
# Split letters from digits: atto3 -> atto 3, mg4 -> mg 4, אטו3 -> אטו 3.
_LETTER_DIGIT = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _NIQQUD.sub("", text).lower().translate(_FINAL_LETTERS)
    text = _GENDER_SUFFIX.sub("", text.strip())
    text = _IN_WORD.sub("", text)
    text = _PUNCTUATION.sub(" ", text)
    text = _LETTER_DIGIT.sub(" ", text)
    return " ".join(text.split())
