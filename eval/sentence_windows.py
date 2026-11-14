"""Premisas NLI por ventanas de frases, sin tocar la ingesta ni el producto.

Compara el verificador NLI con la premisa completa (chunk de 800/120) contra
una variante con premisas mas pequenas: cada chunk se segmenta en frases de
forma determinista y cada ventana une una frase con su anterior contigua.
Se puntuan todas las ventanas y se agregan los maximos de entailment y de
contradiction por separado, con la misma precedencia y umbrales que el
baseline. Experimento de desarrollo, post hoc y con etiquetas de IA sin
revision humana: no valida ninguna mejora ni se integra en ``src/``.

Como maneja cada fenomeno:

- Abreviaturas: la frontera exige punto mas blanco mas mayuscula o signo de
  apertura, asi que "3.14" o "art.5" no se cortan (no hay blanco). Una
  abreviatura seguida de mayuscula ("Sr. Garcia") si se corta: es un
  sobre-segmentado conocido. La ventana con frase anterior mitiga el dano
  porque la segunda ventana vuelve a unir "Sr." con "Garcia ...".
- Decimales y porcentajes: "43 %" o "3,14" no contienen frontera; "v. 2.0"
  solo se corta si hay blanco tras el punto y mayuscula despues.
- Saltos de PDF: saltos de linea, retornos y tabuladores colapsan a un
  espacio antes de segmentar; los guiones de fin de linea del PDF se
  conservan tal cual (no se reconstruyen palabras partidas: limitacion).
- Anafora: la ventana ``anterior + actual`` conserva el antecedente cuando
  esta en la frase inmediata ("Este importe ..."); si esta dos frases
  atras, la ventana no lo cubre (limitacion documentada, no corregida).
- Contexto: solo la frase contigua anterior, nunca la posterior ni todo el
  chunk. Cada frase aparece en dos ventanas como maximo (sola de inicio o
  acompanada), sin seleccion semantica.
- Limites: texto vacio o solo blancos falla; mas de
  ``MAX_SENTENCES_PER_PREMISE`` frases falla en lugar de truncar en
  silencio. Ningun segmento se descarta: la primera frase va sola y cada
  frase posterior genera su ventana con la anterior.
"""

import re
from itertools import pairwise

MAX_SENTENCES_PER_PREMISE = 60

_ABBREVIATIONS = (
    "Sr",
    "Sra",
    "Dr",
    "Dra",
    "Prof",
    "Núm",
    "núm",
    "Pág",
    "pág",
    "Vol",
    "Art",
    "art",
    "Av",
    "D",
    "Dña",
    "Ud",
    "Uds",
    "Ej",
    "ej",
    "p",
)

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'\u201c\u2018\(\[¿¡A-ZÁÉÍÓÚÑ0-9])")
_WHITESPACE = re.compile(r"\s+")


def split_sentences(text: str) -> list[str]:
    """Divide un texto en frases sin dependencias nuevas ni modelo.

    Colapsa blancos (saltos de PDF incluidos) y corta tras ``.``, ``!`` o
    ``?`` seguidos de blanco y mayuscula, digito o signo de apertura. Los
    puntos de abreviaturas comunes ante mayuscula se protegen antes de
    cortar. Falla con texto vacio en lugar de devolver una lista vacia.
    """
    if not text.strip():
        raise ValueError("Premise must not be blank")
    guarded = text
    for abbr in _ABBREVIATIONS:
        pattern = re.compile(r"\b" + re.escape(abbr) + r"\.(?=\s+[A-ZÁÉÍÓÚÑ])")
        guarded = pattern.sub(abbr + "\ue002", guarded)
    normalized = _WHITESPACE.sub(" ", guarded.strip())
    if not normalized:
        raise ValueError("Premise must not be blank")
    parts = _SENTENCE_BOUNDARY.split(normalized)
    sentences = [_WHITESPACE.sub(" ", part).strip().replace("\ue002", ".") for part in parts]
    sentences = [sentence for sentence in sentences if sentence]
    if not sentences:
        raise ValueError("Premise must contain at least one sentence")
    if len(sentences) > MAX_SENTENCES_PER_PREMISE:
        raise ValueError("Too many sentences in premise")
    return sentences


def build_sentence_windows(sentences: list[str]) -> list[str]:
    """Construye una ventana por frase: la primera sola, cada resto con su anterior.

    Incluye todas las ventanas sin seleccion ni descarte. Falla con lista
    vacia o con frases vacias en lugar de omitirlas en silencio.
    """
    if not sentences:
        raise ValueError("Sentence list must not be empty")
    if any(not sentence.strip() for sentence in sentences):
        raise ValueError("Sentences must not be blank")
    windows = [sentences[0].strip()]
    for previous, current in pairwise(sentences):
        windows.append(previous.strip() + " " + current.strip())
    return windows


def build_premise_windows(premise: str) -> list[str]:
    """Segmenta una premisa y devuelve sus ventanas con contexto anterior."""
    return build_sentence_windows(split_sentences(premise))


def expand_window_pairs(
    premises_windows: list[list[str]], hypotheses: list[str]
) -> tuple[list[str], list[str], list[int]]:
    """Expande cada afirmacion contra todas las ventanas de su premisa.

    Devuelve premisas, hipotesis y el indice de afirmacion de cada par, con
    el mismo orden para alinear las puntuaciones del verificador.
    """
    if len(premises_windows) != len(hypotheses):
        raise ValueError("Premises and hypotheses must align")
    pair_premises: list[str] = []
    pair_hypotheses: list[str] = []
    pair_owner: list[int] = []
    for claim_index, (windows, hypothesis) in enumerate(
        zip(premises_windows, hypotheses, strict=True)
    ):
        if not windows:
            raise ValueError("Each premise must produce at least one window")
        if not hypothesis.strip():
            raise ValueError("Hypothesis must not be blank")
        for window in windows:
            if not window.strip():
                raise ValueError("Window must not be blank")
            pair_premises.append(window)
            pair_hypotheses.append(hypothesis)
            pair_owner.append(claim_index)
    return pair_premises, pair_hypotheses, pair_owner


def aggregate_window_scores(
    window_scores: list[tuple[float, float]], pair_owner: list[int], claim_count: int
) -> list[tuple[float, float]]:
    """Agrega maximos separados de entailment y contradiction por afirmacion.

    Cada afirmacion conserva el maximo de entailment sobre sus ventanas y el
    maximo de contradiction sobre las mismas, igual que el baseline conserva
    maximos sobre ventanas de tokens largos.
    """
    if len(window_scores) != len(pair_owner):
        raise ValueError("Window scores and ownership must align")
    if claim_count <= 0:
        raise ValueError("Claim count must be positive")
    best_ent = [0.0] * claim_count
    best_contra = [0.0] * claim_count
    seen = [False] * claim_count
    for (ent, contra), claim_index in zip(window_scores, pair_owner, strict=True):
        if not 0 <= claim_index < claim_count:
            raise ValueError("Pair owner out of range")
        if not seen[claim_index]:
            best_ent[claim_index] = ent
            best_contra[claim_index] = contra
            seen[claim_index] = True
        else:
            best_ent[claim_index] = max(best_ent[claim_index], ent)
            best_contra[claim_index] = max(best_contra[claim_index], contra)
    if not all(seen):
        raise ValueError("Every claim must own at least one window")
    return list(zip(best_ent, best_contra, strict=True))


def decide_verdict(
    entailment: float,
    contradiction: float,
    *,
    supported_threshold: float,
    weak_threshold: float,
    contradiction_threshold: float,
) -> tuple[str, float]:
    """Aplica la misma precedencia y umbrales que el baseline y ``/verify``.

    La contradiction sobre su umbral prevalece incluso si otra ventana
    respalda la afirmacion; despues respaldo, respaldo debil y resto sin
    respaldo. El score es el maximo de contradiction para ``contradicted``
    y el maximo de entailment en los demas casos.
    """
    if contradiction >= contradiction_threshold:
        return "contradicted", contradiction
    if entailment >= supported_threshold:
        return "supported", entailment
    if entailment >= weak_threshold:
        return "weak", entailment
    return "unsupported", entailment
