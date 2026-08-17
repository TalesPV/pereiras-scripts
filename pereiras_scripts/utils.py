"""Funções utilitárias de uso geral."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any


def flatten(iterable: Iterable[Any], *, depth: int = 1) -> list[Any]:
    """Achata uma lista aninhada até a profundidade indicada.

    Args:
        iterable: Iterável a ser achatado.
        depth: Profundidade máxima de achatamento (padrão: 1).

    Returns:
        Lista achatada.

    Examples:
        >>> flatten([[1, 2], [3, [4, 5]]])
        [1, 2, 3, [4, 5]]
        >>> flatten([[1, [2, [3]]], [4]], depth=2)
        [1, 2, [3], 4]
    """
    result: list[Any] = []
    for item in iterable:
        if isinstance(item, Iterable) and not isinstance(item, (str, bytes)) and depth > 0:
            result.extend(flatten(item, depth=depth - 1))
        else:
            result.append(item)
    return result


def chunk(iterable: Iterable[Any], size: int) -> list[list[Any]]:
    """Divide um iterável em lotes de tamanho fixo.

    Args:
        iterable: Iterável a ser dividido.
        size: Tamanho de cada lote. Deve ser maior que zero.

    Returns:
        Lista de lotes.

    Raises:
        ValueError: Se *size* for menor ou igual a zero.

    Examples:
        >>> chunk([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    if size <= 0:
        raise ValueError("size deve ser maior que zero")
    items = list(iterable)
    return [items[i : i + size] for i in range(0, len(items), size)]


def unique(iterable: Iterable[Any]) -> list[Any]:
    """Remove duplicatas preservando a ordem de inserção.

    Args:
        iterable: Iterável com possíveis valores duplicados.

    Returns:
        Lista sem duplicatas, na ordem original.

    Examples:
        >>> unique([3, 1, 2, 1, 3])
        [3, 1, 2]
    """
    seen: set[Any] = set()
    result: list[Any] = []
    for item in iterable:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def safe_get(obj: Any, *keys: str | int, default: Any = None) -> Any:
    """Acessa valores aninhados de dicionários/listas sem lançar exceções.

    Args:
        obj: Objeto raiz (dict, list, ou qualquer objeto com ``__getitem__``).
        *keys: Chaves ou índices a percorrer em sequência.
        default: Valor retornado se algum acesso falhar (padrão: None).

    Returns:
        O valor encontrado ou *default*.

    Examples:
        >>> safe_get({"a": {"b": 1}}, "a", "b")
        1
        >>> safe_get({"a": {"b": 1}}, "a", "c", default=0)
        0
        >>> safe_get([1, [2, 3]], 1, 0)
        2
    """
    current = obj
    for key in keys:
        try:
            current = current[key]
        except (KeyError, IndexError, TypeError):
            return default
    return current


def slugify(text: str) -> str:
    """Converte uma string em slug (minúsculas, sem acentos, separado por hífens).

    A conversão usa normalização NFKD seguida de codificação ASCII, portanto
    caracteres que decompõem em uma base ASCII (ex.: ``é`` → ``e``, ``ã`` → ``a``)
    são transliterados corretamente. Caracteres sem base ASCII equivalente
    (ex.: ``ł``, ``ß``) são silenciosamente removidos.

    Args:
        text: Texto de entrada.

    Returns:
        Slug gerado a partir do texto, ou string vazia se *text* não contiver
        caracteres ASCII válidos.

    Examples:
        >>> slugify("Olá, Mundo!")
        'ola-mundo'
        >>> slugify("Python é incrível")
        'python-e-incrivel'
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    return slug.strip("-")
