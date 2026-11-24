"""Utilidades de texto en español: limpieza, tokenización léxica y números."""
import html
import re
import unicodedata

try:
    from nltk.stem.snowball import SnowballStemmer
    _STEMMER = SnowballStemmer("spanish")
except Exception:  # nltk no disponible: se usa un stemmer nulo
    _STEMMER = None

STOPWORDS = set("""
a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
durante e el ella ellas ellos en entre era es esa esas ese eso esos esta estas este
esto estos fue ha hay la las le les lo los mas me mi mis muy ni no nos o os otra otro
para pero poco por porque que quien se sea ser si sin sobre su sus tambien te tiene
todo todos tu tus un una unas uno unos y ya yo the and for with of to in
""".split())


def strip_html(text):
    if not text:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"<br\s*/?>", ". ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_accents(text):
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text):
    return strip_accents(str(text).lower())


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)?")


def tokenize(text, stem=True):
    """Tokenizador para BM25: minúsculas, sin acentos, sin stopwords y con stemming Snowball."""
    toks = _TOKEN_RE.findall(normalize(text))
    toks = [t for t in toks if t not in STOPWORDS and (len(t) > 1 or t.isdigit())]
    if stem and _STEMMER is not None:
        toks = [_STEMMER.stem(t) if not t[0].isdigit() else t for t in toks]
    return toks


# ---------------------------------------------------------------------------
# Números en español (el ASR a veces escribe "tres" y a veces "3")
# ---------------------------------------------------------------------------
_UNITS = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintiun": 21,
    "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
    "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100,
    "doscientos": 200, "doscientas": 200, "trescientos": 300, "trescientas": 300,
    "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
    "seiscientos": 600, "seiscientas": 600, "setecientos": 700, "setecientas": 700,
    "ochocientos": 800, "ochocientas": 800, "novecientos": 900, "novecientas": 900,
    "media": 0.5, "medio": 0.5,
}


def words_to_number(words):
    """Convierte una secuencia de palabras numéricas ('ciento cincuenta y dos') en número."""
    total, current, seen = 0, 0, False
    for w in words:
        if w == "y":
            continue
        if w == "mil":
            current = max(current, 1) * 1000
            total += current
            current = 0
            seen = True
        elif w == "docena":                       # multiplicador: "media docena" = 6
            current = (current or 1) * 12
            seen = True
        elif w in _UNITS:
            current += _UNITS[w]
            seen = True
        else:
            return None
    return total + current if seen else None


def spanish_numbers_to_digits(text):
    """Reescribe números escritos con palabras como dígitos ('tres mochilas' -> '3 mochilas')."""
    tokens = re.findall(r"\w+|[^\w\s]+|\s+", text)
    out, buf = [], []

    def flush():
        if not buf:
            return
        words = [normalize(t) for t in buf if t.strip()]
        # Quitar "y" final que no forma parte del número
        trailing_y = words and words[-1] == "y"
        if trailing_y:
            words = words[:-1]
        val = words_to_number(words) if words else None
        if val is not None and not (len(words) == 1 and words[0] in ("un", "una", "uno", "media", "medio")):
            val = int(val) if float(val).is_integer() else val
            out.append(str(val))
            if trailing_y:
                out.append(" y")
        else:
            out.extend(buf)
        buf.clear()

    for tok in tokens:
        n = normalize(tok)
        if n in _UNITS or n in ("mil", "docena") or (n == "y" and buf):
            buf.append(tok)
        elif tok.isspace() and buf:
            buf.append(tok)
        else:
            # Devolver los espacios finales del buffer antes de cerrar
            trailing = []
            while buf and buf[-1].isspace():
                trailing.append(buf.pop())
            flush()
            out.extend(reversed(trailing))
            out.append(tok)
    trailing = []
    while buf and buf[-1].isspace():
        trailing.append(buf.pop())
    flush()
    out.extend(reversed(trailing))
    return "".join(out)


_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def extract_numbers(text):
    """Lista de números (float) presentes en un texto, tras convertir palabras a dígitos."""
    t = spanish_numbers_to_digits(text)
    vals = []
    for m in _NUM_RE.findall(t):
        try:
            vals.append(float(m.replace(",", ".")))
        except ValueError:
            pass
    return vals


_MONEY_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:€|euros?|eur)\b|(?:€)\s*(\d+(?:[.,]\d+)?)", re.I)


def extract_amounts(text):
    """Importes monetarios mencionados ('50 euros', '€30')."""
    t = spanish_numbers_to_digits(text)
    vals = []
    for a, b in _MONEY_RE.findall(t):
        v = a or b
        vals.append(float(v.replace(",", ".")))
    return vals


def extract_quantities(text):
    """Cantidades: números que NO son importes monetarios."""
    nums = extract_numbers(text)
    amounts = extract_amounts(text)
    rest = list(nums)
    for a in amounts:
        if a in rest:
            rest.remove(a)
    return rest


# "si" solo cuenta al inicio del mensaje (evita el condicional "¿y si compro…?"); verbos como
# "comprar" no cuentan como confirmación ("quiero comprar…" es una petición, no un sí).
AFFIRMATIVE_RE = re.compile(
    r"^\W*(si|vale|ok|okay|dale|claro|perfecto|correcto|de acuerdo)\b|\b(confirm\w*|adelante|procede\w*|hazlo)\b",
    re.I)
NEGATIVE_RE = re.compile(r"\b(no|cancela\w*|espera\w*|todavia no|aun no|mejor no|cambia\w*)\b", re.I)


def is_explicit_confirmation(text):
    """Detección por código de una confirmación explícita del usuario.

    Se exige un término afirmativo y ningún término negativo/de cambio, para que
    frases como "no, cambia la cantidad" nunca disparen un pedido.
    """
    t = normalize(text)
    return bool(AFFIRMATIVE_RE.search(t)) and not NEGATIVE_RE.search(t)


# ---------------------------------------------------------------------------
# Texto para síntesis de voz: cifras en palabras (XTTS pronuncia mal "7,99" o "2 ×")
# ---------------------------------------------------------------------------
_W_UNITS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once",
            "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte",
            "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
            "veintiocho", "veintinueve"]
_W_TENS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}
_W_HUNDREDS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
               6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def number_to_words(n):
    """Entero 0..999 999 en palabras (1250 -> 'mil doscientos cincuenta')."""
    n = int(n)
    if n < 0 or n > 999_999:
        return str(n)
    if n < 30:
        return _W_UNITS[n]
    if n < 100:
        t, u = divmod(n, 10)
        return _W_TENS[t * 10] + (f" y {_W_UNITS[u]}" if u else "")
    if n == 100:
        return "cien"
    if n < 1000:
        h, r = divmod(n, 100)
        return _W_HUNDREDS[h] + (f" {number_to_words(r)}" if r else "")
    m, r = divmod(n, 1000)
    head = "mil" if m == 1 else _apocope(number_to_words(m)) + " mil"
    return head + (f" {number_to_words(r)}" if r else "")


def _apocope(words):
    # Ante un sustantivo: "veintiuno euros" -> "veintiún euros", "uno euro" -> "un euro"
    return re.sub(r"veintiuno$", "veintiún", re.sub(r"\buno$", "un", words))


_SPOKEN_MONEY_RE = re.compile(r"(?<![\w.,])(\d{1,6})(?:,(\d{2}))?\s*euros?\b", re.I)
_SPOKEN_INT_RE = re.compile(r"(?<![\w.,])(\d{1,4})(?![\w]|[.,]\d)")


def spoken_numbers(text):
    """Reescribe importes y enteros sueltos en palabras para el TTS.

    '2 unidades a 7,99 euros' -> 'dos unidades a siete con noventa y nueve euros'. No toca códigos
    alfanuméricos ('A5', 'USB3') ni decimales que no sean importes ('2.0').
    """
    def money(m):
        whole, cents = int(m.group(1)), m.group(2)
        has_cents = bool(cents and int(cents))
        txt = _apocope(number_to_words(whole))
        if has_cents:
            txt += " con " + number_to_words(int(cents))
        return f"{txt} {'euro' if whole == 1 and not has_cents else 'euros'}"

    text = _SPOKEN_MONEY_RE.sub(money, text)
    return _SPOKEN_INT_RE.sub(lambda m: number_to_words(m.group(1)), text)


_TITLE_TAIL = {"de", "del", "a", "al", "con", "para", "por", "y", "e", "o", "en", "la", "el", "los", "las", "un", "una"}


def short_title(title, max_words=6):
    """Título corto para leer en voz alta: sin corchetes ni paréntesis, y sin terminar en preposición o artículo."""
    words = re.split(r"\s*[\[(]", str(title), maxsplit=1)[0].split()[:max_words]
    while words and (normalize(words[-1]).strip(".,;:") in _TITLE_TAIL or not re.search(r"\w", words[-1])):
        words.pop()
    if words:
        words[-1] = words[-1].rstrip(",;:")
    return " ".join(words) or " ".join(str(title).split()[:max_words])
