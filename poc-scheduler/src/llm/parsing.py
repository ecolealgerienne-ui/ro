"""Helpers de parsing pour les reponses LLM.

Les modeles ont tendance a entourer leur JSON de prose ("Voici la reponse :",
"```json", etc.) malgre les instructions du prompt. Ces helpers extraient
le bloc JSON robustement.
"""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


class LLMParseError(ValueError):
    """Le contenu LLM n'a pas pu etre parse en JSON."""


def extract_json_block(content: str) -> Any:
    """Extrait le premier bloc JSON parsable d'une chaine de texte.

    Strategie en cascade :
    1. Bloc dans ```json ... ``` ou ``` ... ```
    2. Premier objet `{...}` ou tableau `[...]` complet detecte par
       parsing brace-aware (ignore les accolades dans les strings)
    3. Tentative de json.loads sur la chaine entiere

    Raises:
        LLMParseError: si aucune strategie ne donne de JSON valide.
    """
    if not content or not content.strip():
        raise LLMParseError("Contenu vide")

    # 1. Bloc ```...```
    for match in _JSON_FENCE_RE.finditer(content):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # 2. Premier { ou [ equilibre
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = content.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(content)):
            c = content[i]
            if in_str:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == opener:
                    depth += 1
                elif c == closer:
                    depth -= 1
                    if depth == 0:
                        candidate = content[start : i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break

    # 3. Fallback : la chaine entiere
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMParseError(
            f"Impossible d'extraire un JSON valide. Premieres 200 chars : "
            f"{content[:200]!r}. Erreur : {e}"
        ) from e
