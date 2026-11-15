"""Os domínios de valores das colunas, declarados uma vez (F7; Q15 e Q18 do plano da base dos consumidores).

── O que é declaração e o que é derivado ───────────────────────────────────────
O **catálogo** `docs/glossario_de_negocio/dominios.yml` declara cada domínio uma vez: o nome em inglês, a
descrição e o mapa valor → significado em português, com a fonte de cada significado. A **ligação** é
declarada na coluna, no `.yml` escrito à mão de `analytics` e de `consumption`:

    meta:
      value_domain: order_status
      null_meaning: "…"          # só se a coluna admite nulo; sem ele, a coluna ganha `not_null`
      impossible: {paid: "…"}    # valores do domínio que não podem aparecer nesse papel, com o motivo
      not_observed: {lost: "…"}  # valores possíveis que o dado ainda não tem nessa coluna, com o motivo

Do catálogo e da ligação, `make catalog` **deriva** na coluna:

* `meta.values` — o mapa, menos os impossíveis;
* o `accepted_values` com exatamente esses valores, marcado por `config.meta.value_domain` para ser
  reconhecido como derivado (e removido se a ligação sair);
* o `not_null`, quando a ligação não tem `null_meaning`.

O derivado não se edita à mão. O escritor é o de linhas de `sensitivity`, estendido para substituir a
subárvore inteira (`meta.values`, o item do `accepted_values`) — nunca linha a linha, que deixaria filhos
antigos. Chave e valor saem entre aspas duplas (a forma JSON, que é YAML válido): o código `00` continua
texto, e o significado com quebra de linha ou dois-pontos não muda de forma.
"""

from __future__ import annotations

import json
import pathlib
from collections import defaultdict
from dataclasses import dataclass, field

from mvp_ed1.models import sensitivity

CATALOG = sensitivity.ROOT / "docs" / "glossario_de_negocio" / "dominios.yml"
LAYERS = ("analytics", "consumption")
LINK_KEYS = ("value_domain", "null_meaning", "impossible", "not_observed")


# ── O catálogo ────────────────────────────────────────────────────────────────────

def load_catalog(caminho: pathlib.Path = CATALOG, conteudo: str | None = None) -> dict:
    """O catálogo, lido estrito (chave repetida é erro) e conferido na forma."""
    documento = sensitivity.read_yaml(caminho, conteudo)
    dominios = documento.get("domains")
    if not isinstance(dominios, dict) or not dominios:
        raise ValueError(f"{caminho}: sem `domains`")
    for nome, dominio in dominios.items():
        valores = (dominio or {}).get("values")
        if not isinstance(valores, dict) or not valores:
            raise ValueError(f"{caminho}: domínio `{nome}` sem `values`")
        for valor, significado in valores.items():
            if not isinstance(valor, str):
                raise ValueError(f"{caminho}: `{nome}`: o valor {valor!r} não é texto — escreva-o entre aspas")
            if not isinstance(significado, dict) or not significado.get("meaning") or not significado.get("source"):
                raise ValueError(f"{caminho}: `{nome}.{valor}` sem `meaning` e `source`")
    return documento


# ── As ligações ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Link:
    path: pathlib.Path
    model: str
    column: str
    domain: str
    null_meaning: str | None
    impossible: dict
    not_observed: dict

    @property
    def label(self) -> str:
        return f"{self.model}.{self.column}"


def _camada(caminho: pathlib.Path) -> str | None:
    partes = caminho.relative_to(sensitivity.DBT / "models").parts if caminho.is_relative_to(sensitivity.DBT / "models") else ()
    return partes[0] if partes and partes[0] in LAYERS else None


def links(disco: dict) -> list[Link]:
    """Toda coluna de `analytics` e `consumption` que declara `meta.value_domain`, no `.yml` à mão."""
    saida = []
    for nome, entrada in sorted(disco.items()):
        if _camada(entrada.path) is None:
            continue
        for coluna, declarada in entrada.columns.items():
            meta = declarada.get("meta") or {}
            if "value_domain" not in meta:
                orfas = [k for k in LINK_KEYS if k in meta]
                if orfas:
                    raise ValueError(f"{nome}.{coluna}: {orfas} sem `value_domain`")
                continue
            if entrada.kind != "hand":
                raise ValueError(f"{nome}.{coluna}: `value_domain` fora de um `.yml` à mão ({entrada.path.name})")
            saida.append(Link(entrada.path, nome, coluna, meta["value_domain"], meta.get("null_meaning"),
                              meta.get("impossible") or {}, meta.get("not_observed") or {}))
    return saida


# ── A derivação ───────────────────────────────────────────────────────────────────

@dataclass
class Derived:
    """O que escrever: `.yml` → modelo → coluna → {"values", "accepted", "not_null", "domain"}; e o que remover."""
    patches: dict[pathlib.Path, dict[str, dict[str, dict]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(dict)))
    removals: dict[pathlib.Path, dict[str, list[str]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(list)))


def allowed(link: Link, catalogo: dict) -> dict[str, str]:
    """Os valores permitidos na coluna — o domínio menos os impossíveis — com o significado."""
    dominio = catalogo["domains"].get(link.domain)
    if dominio is None:
        raise ValueError(f"{link.label}: domínio `{link.domain}` não existe no catálogo")
    valores = dominio["values"]
    if fora := sorted(set(link.impossible) - set(valores)):
        raise ValueError(f"{link.label}: `impossible` cita valores fora do domínio `{link.domain}`: {fora}")
    if fora := sorted(set(link.not_observed) - set(valores)):
        raise ValueError(f"{link.label}: `not_observed` cita valores fora do domínio `{link.domain}`: {fora}")
    if ambos := sorted(set(link.impossible) & set(link.not_observed)):
        raise ValueError(f"{link.label}: {ambos} estão em `impossible` e em `not_observed`")
    for chave, motivos in (("impossible", link.impossible), ("not_observed", link.not_observed)):
        if not isinstance(motivos, dict) or not all(isinstance(m, str) and m.strip() for m in motivos.values()):
            raise ValueError(f"{link.label}: `{chave}` é um mapa valor → motivo, com motivo escrito")
    return {v: s["meaning"] for v, s in valores.items() if v not in link.impossible}


def derive(catalogo: dict, ligacoes: list[Link], disco: dict) -> Derived:
    saida = Derived()
    for link in ligacoes:
        permitidos = allowed(link, catalogo)
        saida.patches[link.path][link.model][link.column] = {
            "domain": link.domain, "values": permitidos, "accepted": sorted(permitidos),
            "not_null": link.null_meaning is None}
    ligadas = {(l.model, l.column) for l in ligacoes}
    for nome, entrada in disco.items():
        if _camada(entrada.path) is None or entrada.kind != "hand":
            continue
        for coluna, declarada in entrada.columns.items():
            meta = declarada.get("meta") or {}
            derivado = "values" in meta or any(_marcado(t) for t in declarada.get("data_tests") or [])
            if derivado and (nome, coluna) not in ligadas:
                saida.removals[entrada.path][nome].append(coluna)
    return saida


def orphan_domains(catalogo: dict, ligacoes: list[Link]) -> list[str]:
    """Domínios que nenhuma coluna liga e não estão reservados (RVB5-2-03)."""
    usados = {l.domain for l in ligacoes}
    return sorted(n for n, d in catalogo["domains"].items() if n not in usados and not (d or {}).get("reserved"))


def _marcado(teste) -> bool:
    if not isinstance(teste, dict) or "accepted_values" not in teste:
        return False
    corpo = teste["accepted_values"] or {}
    return "value_domain" in ((corpo.get("config") or {}).get("meta") or {})


# ── O escritor ────────────────────────────────────────────────────────────────────

def _q(texto: str) -> str:
    return json.dumps(texto, ensure_ascii=False)


def _item_da_coluna(linhas: list[str], modelo: str, coluna: str) -> tuple[int, int, int]:
    """(início, fim, recuo) do item `- name: <coluna>` do modelo; recusa o que o escritor não edita."""
    from mvp_ed1.models.sensitivity import _block_end, _chave_columns, _coluna, _indent, _locate
    inicio = _locate(linhas, modelo)
    if inicio is None:
        raise KeyError(f"entrada `{modelo}` não encontrada")
    base = _indent(linhas[inicio])
    fim = _block_end(linhas, inicio, base)
    bloco = linhas[inicio:fim]
    idx_cols = _chave_columns(bloco, base)
    if idx_cols is None:
        raise KeyError(f"`{modelo}` sem `columns:`")
    idx, recuo, _ = _coluna(bloco, idx_cols, coluna, modelo)
    if idx is None:
        raise KeyError(f"`{modelo}.{coluna}` não está no `.yml`")
    return inicio + idx, inicio + _block_end(bloco, idx, recuo), recuo


def _subchave(linhas: list[str], ini: int, fim: int, recuo: int, chave: str) -> tuple[int | None, int]:
    """A linha `chave:` no recuo dado entre `ini` e `fim`, e o fim do bloco dela; recusa a forma em linha."""
    from mvp_ed1.models.sensitivity import _block_end
    for i in range(ini, fim):
        texto = linhas[i]
        if sensitivity._indent(texto) == recuo and texto.split("#", 1)[0].strip().startswith(f"{chave}:"):
            if texto.split("#", 1)[0].strip() != f"{chave}:":
                raise ValueError(f"`{chave}` escrito em linha (linha {i + 1}); escreva-o em bloco para o gerador editar")
            return i, min(_block_end(linhas, i, recuo), fim)
    return None, fim


def _itens_da_lista(linhas: list[str], ini: int, fim: int) -> list[tuple[int, int]]:
    """Os itens `- …` da lista entre `ini` (a linha da chave) e `fim`: (início, fim) de cada um."""
    itens = []
    filhos = [i for i in range(ini + 1, fim) if sensitivity._ativa(linhas[i])]
    if not filhos:
        return itens
    coluna = sensitivity._indent(linhas[filhos[0]])
    comecos = [i for i in filhos if sensitivity._indent(linhas[i]) == coluna and linhas[i].strip().startswith("- ")]
    for k, c in enumerate(comecos):
        itens.append((c, comecos[k + 1] if k + 1 < len(comecos) else fim))
    return itens


def _recuar(linhas: list[str], ini: int, fim: int) -> int:
    """O fim do bloco sem as linhas vazias e os comentários soltos do fim, que pertencem ao que vem depois."""
    while fim > ini + 1 and not sensitivity._ativa(linhas[fim - 1]):
        fim -= 1
    return fim


def _e_teste(linha: str, nome: str) -> bool:
    texto = linha.split("#", 1)[0].strip()
    return texto in (f"- {nome}", f"- {nome}:") or texto.startswith(f"- {nome}:")


def patch_value_domains(texto: str, entradas: dict[str, dict[str, dict]], remocoes: dict[str, list[str]] | None = None) -> str:
    """Escreve, em cada coluna pedida, a subárvore `meta.values`, o `accepted_values` derivado e o `not_null`."""
    linhas = texto.split("\n")
    for modelo, colunas in entradas.items():
        for coluna, pedido in colunas.items():
            ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
            # meta.values: a subárvore inteira
            idx_meta, fim_meta = _subchave(linhas, ini + 1, fim, recuo + 2, "meta")
            if idx_meta is None:
                raise ValueError(f"`{modelo}.{coluna}` sem `meta` em bloco (a ligação vive nele)")
            idx_val, fim_val = _subchave(linhas, idx_meta + 1, fim_meta, recuo + 4, "values")
            novo = [" " * (recuo + 4) + "values:"] + [" " * (recuo + 6) + f"{_q(v)}: {_q(s)}" for v, s in sorted(pedido["values"].items())]
            if idx_val is None:
                ponto = _recuar(linhas, idx_meta, fim_meta)
                linhas[ponto:ponto] = novo
            else:
                linhas[idx_val:_recuar(linhas, idx_val, fim_val)] = novo
            ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
            # data_tests: o accepted_values derivado e o not_null
            if _subchave(linhas, ini + 1, fim, recuo + 2, "tests")[0] is not None:
                raise ValueError(f"`{modelo}.{coluna}` usa `tests:`; o projeto escreve `data_tests:`")
            idx_t, fim_t = _subchave(linhas, ini + 1, fim, recuo + 2, "data_tests")
            if idx_t is None:
                ponto = _recuar(linhas, ini, fim)
                linhas[ponto:ponto] = [" " * (recuo + 2) + "data_tests:"]
                ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
                idx_t, fim_t = _subchave(linhas, ini + 1, fim, recuo + 2, "data_tests")
            itens = _itens_da_lista(linhas, idx_t, fim_t)
            recuo_item = sensitivity._indent(linhas[itens[0][0]]) if itens else recuo + 4
            aceitos = [(a, b) for a, b in itens if _e_teste(linhas[a], "accepted_values")]
            nulos = [(a, b) for a, b in itens if _e_teste(linhas[a], "not_null")]
            if len(aceitos) > 1:
                raise ValueError(f"`{modelo}.{coluna}` tem {len(aceitos)} `accepted_values`")
            if nulos and not pedido["not_null"]:
                raise ValueError(f"`{modelo}.{coluna}`: `not_null` à mão, mas a ligação declara `null_meaning`")
            bloco_av = [
                " " * recuo_item + "- accepted_values:",
                " " * (recuo_item + 4) + "arguments:",
                " " * (recuo_item + 6) + "values: [" + ", ".join(_q(v) for v in pedido["accepted"]) + "]",
                " " * (recuo_item + 4) + "config:",
                " " * (recuo_item + 6) + "meta:",
                " " * (recuo_item + 8) + f"value_domain: {pedido['domain']}",
            ]
            if aceitos:
                a, b = aceitos[0]
                linhas[a:_recuar(linhas, a, b)] = bloco_av
            else:
                ponto = _recuar(linhas, idx_t, fim_t)
                linhas[ponto:ponto] = bloco_av
            if pedido["not_null"] and not nulos:
                ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
                idx_t, _ = _subchave(linhas, ini + 1, fim, recuo + 2, "data_tests")
                linhas.insert(idx_t + 1, " " * recuo_item + "- not_null")
    for modelo, colunas in (remocoes or {}).items():
        for coluna in colunas:
            ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
            idx_meta, fim_meta = _subchave(linhas, ini + 1, fim, recuo + 2, "meta")
            if idx_meta is not None:
                idx_val, fim_val = _subchave(linhas, idx_meta + 1, fim_meta, recuo + 4, "values")
                if idx_val is not None:
                    del linhas[idx_val:_recuar(linhas, idx_val, fim_val)]
            ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
            idx_t, fim_t = _subchave(linhas, ini + 1, fim, recuo + 2, "data_tests")
            if idx_t is not None:
                for a, b in reversed(_itens_da_lista(linhas, idx_t, fim_t)):
                    if _e_teste(linhas[a], "accepted_values") and "value_domain:" in "\n".join(linhas[a:b]):
                        del linhas[a:_recuar(linhas, a, b)]
    return "\n".join(linhas)


def verify(caminho: pathlib.Path, conteudo: str, entradas: dict[str, dict[str, dict]],
           remocoes: dict[str, list[str]] | None = None) -> None:
    """O arquivo escrito, como o YAML o carrega, diz o que se pediu — nos dois modos (RVL3-4-01)."""
    documento = sensitivity.read_yaml(caminho, conteudo)
    por_nome = sensitivity.entries_by_address(documento)
    for modelo, colunas in entradas.items():
        cols = {c["name"]: c for c in (por_nome.get(modelo) or {}).get("columns", [])}
        for coluna, pedido in colunas.items():
            c = cols.get(coluna) or {}
            if (c.get("meta") or {}).get("values") != pedido["values"]:
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}` não ficou com o `meta.values` do catálogo")
            testes = c.get("data_tests") or []
            av = [t for t in testes if _marcado(t)]
            if len(av) != 1 or (av[0]["accepted_values"].get("arguments") or {}).get("values") != pedido["accepted"]:
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}` não ficou com o `accepted_values` do catálogo")
            if pedido["not_null"] != ("not_null" in testes):
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}`: `not_null` diverge da ligação")
    for modelo, colunas in (remocoes or {}).items():
        cols = {c["name"]: c for c in (por_nome.get(modelo) or {}).get("columns", [])}
        for coluna in colunas:
            c = cols.get(coluna) or {}
            if "values" in (c.get("meta") or {}) or any(_marcado(t) for t in c.get("data_tests") or []):
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}` ainda tem o derivado de uma ligação que saiu")
