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
      unknown_member: dim_geography.region   # só na coluna que propaga o membro desconhecido de outra relação

Do catálogo e da ligação, `make catalog` **deriva** na coluna:

* `meta.values` — o mapa, menos os impossíveis;
* o `accepted_values` com exatamente esses valores, marcado por `config.meta.value_domain` para ser
  reconhecido como derivado (e removido se a ligação sair);
* o `not_null`, quando a ligação não tem `null_meaning`.

O **membro desconhecido** não entra no domínio: o sentinela dele (`unknown`, `Desconhecido`) é da linha de
aterrissagem de uma dimensão, não um valor do negócio. O catálogo o declara por dimensão
(`unknown_members`); a coluna da própria dimensão o herda, e a coluna que o propaga — a view que agrupa
pela região da geografia — o declara com `unknown_member: <dimensão>.<coluna>`. Assim as colunas que nunca
o têm não precisam repeti-lo como impossível.

O derivado não se edita à mão. O escritor é o de linhas de `sensitivity`, estendido para substituir a
subárvore inteira (`meta.values`, o item do `accepted_values`) — nunca linha a linha, que deixaria filhos
antigos. Chave e valor saem entre aspas duplas (a forma JSON, que é YAML válido): o código `00` continua
texto, e o significado com quebra de linha ou dois-pontos não muda de forma.
"""

from __future__ import annotations

import json
import pathlib
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field

import yaml

from mvp_ed1.models import sensitivity

CATALOG_RELATIVE = pathlib.Path("docs") / "glossario_de_negocio" / "dominios.yml"
CATALOG = sensitivity.ROOT / CATALOG_RELATIVE
LAYERS = ("analytics", "consumption")
LINK_KEYS = ("value_domain", "null_meaning", "impossible", "not_observed", "unknown_member")


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
    membros = documento.get("unknown_members") or {}
    if not isinstance(membros, dict):
        raise ValueError(f"{caminho}: `unknown_members` é um mapa dimensão → membro")
    for dimensao, membro in membros.items():
        if not isinstance(membro, dict) or not membro.get("meaning") or not membro.get("source"):
            raise ValueError(f"{caminho}: membro desconhecido de `{dimensao}` sem `meaning` e `source`")
        colunas = membro.get("columns")
        if not isinstance(colunas, dict) or not colunas:
            raise ValueError(f"{caminho}: membro desconhecido de `{dimensao}` sem `columns`")
        for coluna, valor in colunas.items():
            if not isinstance(valor, str):
                raise ValueError(f"{caminho}: `{dimensao}.{coluna}`: o sentinela {valor!r} não é texto — escreva-o entre aspas")
    for grupo in ("by_type", "by_name"):
        for nome, regra in ((documento.get("exclusions") or {}).get(grupo) or {}).items():
            if not isinstance(regra, dict) or not regra.get("reason"):
                raise ValueError(f"{caminho}: regra de exclusão `{nome}` sem `reason`")
    for endereco, motivo in ((documento.get("exclusions") or {}).get("exceptions") or {}).items():
        if not isinstance(motivo, str) or not motivo.strip():
            raise ValueError(f"{caminho}: exceção `{endereco}` sem motivo")
    return documento


TEXT_TYPES = frozenset({"text", "character varying", "character"})


def coverage(colunas, ligadas: set[tuple[str, str]], catalogo: dict) -> tuple[dict[str, str], list[str]]:
    """A classificação de cada coluna física (Bloco 5, item 3): `(classificação por endereço, problemas)`.

    `colunas` são `(schema, relação, coluna, tipo)`, como o `information_schema` as dá; `ligadas`, os
    `(relação, coluna)` com `meta.value_domain`. A coluna ligada é `value_domain`; a não ligada cai numa
    exceção nominal, ou em **exatamente uma** regra — de tipo, se não for texto; de nome, se for. Nenhuma
    regra, ou duas, é problema: o oráculo é "N de N colunas classificadas"."""
    regras = catalogo.get("exclusions") or {}
    por_tipo = regras.get("by_type") or {}
    por_nome = regras.get("by_name") or {}
    excecoes = regras.get("exceptions") or {}
    saida: dict[str, str] = {}
    problemas: list[str] = []
    for schema, relacao, coluna, tipo in colunas:
        endereco = f"{schema}.{relacao}.{coluna}"
        if (relacao, coluna) in ligadas:
            saida[endereco] = "value_domain"
            continue
        if f"{relacao}.{coluna}" in excecoes:
            saida[endereco] = "exception"
            continue
        if tipo in TEXT_TYPES:
            casam = [n for n, r in por_nome.items()
                     if coluna in (r.get("names") or []) or any(coluna.endswith(s) for s in r.get("suffixes") or [])]
        else:
            casam = [n for n, r in por_tipo.items() if tipo in (r.get("types") or [])]
        if len(casam) == 1:
            saida[endereco] = casam[0]
        else:
            problemas.append(f"{endereco} ({tipo}): {'nenhuma regra' if not casam else 'duas regras: ' + ', '.join(casam)}")
    return saida, problemas


def sentinel(catalogo: dict, endereco: str) -> tuple[str, str] | None:
    """(valor, significado) do sentinela em `<dimensão>.<coluna>`, ou `None` se a coluna não o tem."""
    dimensao, _, coluna = endereco.partition(".")
    membro = (catalogo.get("unknown_members") or {}).get(dimensao)
    if not membro or coluna not in membro["columns"]:
        return None
    return membro["columns"][coluna], f"Membro desconhecido — {membro['meaning']}"


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
    unknown_member: str | None = None

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
                              meta.get("impossible") or {}, meta.get("not_observed") or {}, meta.get("unknown_member")))
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
    permitidos = {v: s["meaning"] for v, s in valores.items() if v not in link.impossible}
    proprio = sentinel(catalogo, f"{link.model}.{link.column}")
    if link.unknown_member is not None:
        if proprio is not None:
            raise ValueError(f"{link.label}: `unknown_member` sobra — a coluna é da própria dimensão e já herda o sentinela")
        proprio = sentinel(catalogo, link.unknown_member)
        if proprio is None:
            raise ValueError(f"{link.label}: `unknown_member: {link.unknown_member}` não existe em `unknown_members`")
    if proprio is not None:
        valor, significado = proprio
        if valor in valores:
            raise ValueError(f"{link.label}: o sentinela {valor!r} colide com um valor do domínio `{link.domain}`")
        permitidos[valor] = significado
    return permitidos


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


def _marcado(teste, tipo: str | None = None) -> bool:
    """O teste que o escritor deriva: `accepted_values` ou `not_null` com `config.meta.value_domain` (RVB5A-1-02)."""
    if not isinstance(teste, dict) or len(teste) != 1:
        return False
    (chave, corpo), = teste.items()
    if chave not in ("accepted_values", "not_null") or (tipo is not None and chave != tipo):
        return False
    return "value_domain" in (((corpo or {}).get("config") or {}).get("meta") or {})


def _not_null_a_mao(testes) -> bool:
    """O `not_null` escrito à mão e **ativo**: o texto solto, ou o bloco sem a marca do derivado e sem `enabled: false`."""
    return any(t == "not_null" or (isinstance(t, dict) and "not_null" in t and not _marcado(t) and not _desligado(t))
               for t in testes)


def _desligado(teste) -> bool:
    return isinstance(teste, dict) and len(teste) == 1 and \
        (((next(iter(teste.values())) or {}).get("config") or {}).get("enabled") is False)


def _not_null_a_mao_desligado(testes) -> bool:
    """O `not_null` à mão com `enabled: false`: o dbt não o roda (`manifest.add_disabled`), e ele não vale como
    garantia de não nulo (RVB5A-2-02)."""
    return any(isinstance(t, dict) and "not_null" in t and not _marcado(t) and _desligado(t) for t in testes)


def _item_marcado(linhas: list[str], ini: int, fim: int, tipo: str) -> bool:
    """O item da lista é o derivado pela **estrutura** carregada, não pelo texto: um comentário com
    `value_domain:` não o faz derivado (RVB5A-2-01)."""
    try:
        carregado = yaml.safe_load(textwrap.dedent("\n".join(linhas[ini:_recuar(linhas, ini, fim)])))
    except yaml.YAMLError:
        return False
    return isinstance(carregado, list) and len(carregado) == 1 and _marcado(carregado[0], tipo)


def has_derived(disco: dict) -> bool:
    """Se algum `.yml` à mão de `analytics` ou `consumption` tem derivado dos domínios de valores."""
    return any("values" in (c.get("meta") or {}) or any(_marcado(t) for t in c.get("data_tests") or [])
               for e in disco.values() if _camada(e.path) is not None and e.kind == "hand" for c in e.columns.values())


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
            nulos_derivados = [(a, b) for a, b in nulos if _item_marcado(linhas, a, b, "not_null")]
            nulos_a_mao = [x for x in nulos if x not in nulos_derivados]
            if len(aceitos) > 1:
                raise ValueError(f"`{modelo}.{coluna}` tem {len(aceitos)} `accepted_values`")
            if nulos_a_mao and not pedido["not_null"]:
                raise ValueError(f"`{modelo}.{coluna}`: `not_null` à mão, mas a ligação declara `null_meaning`")
            if pedido["not_null"]:
                carregados = yaml.safe_load(textwrap.dedent("\n".join(linhas[idx_t + 1:fim_t]))) or []
                if _not_null_a_mao_desligado(carregados):
                    raise ValueError(f"`{modelo}.{coluna}`: `not_null` à mão desligado (`enabled: false`), mas a ligação exige "
                                     "`not_null` — ligue-o ou tire-o, na declaração")
            bloco_av = [
                " " * recuo_item + "- accepted_values:",
                " " * (recuo_item + 4) + "arguments:",
                " " * (recuo_item + 6) + "values: [" + ", ".join(_q(v) for v in pedido["accepted"]) + "]",
                " " * (recuo_item + 4) + "config:",
                " " * (recuo_item + 6) + "meta:",
                " " * (recuo_item + 8) + f"value_domain: {pedido['domain']}",
            ]
            bloco_nn = [
                " " * recuo_item + "- not_null:",
                " " * (recuo_item + 4) + "config:",
                " " * (recuo_item + 6) + "meta:",
                " " * (recuo_item + 8) + f"value_domain: {pedido['domain']}",
            ]
            # De baixo para cima: o not_null derivado (substituído, removido ou deixado ao à mão) e o accepted_values.
            trocas = []
            if aceitos:
                trocas.append((aceitos[0], bloco_av))
            for item in nulos_derivados:
                trocas.append((item, bloco_nn if pedido["not_null"] and not nulos_a_mao and item == nulos_derivados[0] else []))
            for (a, b), novo in sorted(trocas, key=lambda x: x[0][0], reverse=True):
                linhas[a:_recuar(linhas, a, b)] = novo
            if not aceitos:
                ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
                idx_t, fim_t = _subchave(linhas, ini + 1, fim, recuo + 2, "data_tests")
                ponto = _recuar(linhas, idx_t, fim_t)
                linhas[ponto:ponto] = bloco_av
            if pedido["not_null"] and not nulos_a_mao and not nulos_derivados:
                ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
                idx_t, _ = _subchave(linhas, ini + 1, fim, recuo + 2, "data_tests")
                linhas[idx_t + 1:idx_t + 1] = bloco_nn
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
                    if any(_e_teste(linhas[a], tipo) and _item_marcado(linhas, a, b, tipo)
                           for tipo in ("accepted_values", "not_null")):
                        del linhas[a:_recuar(linhas, a, b)]
                # A lista que perdeu o último item leva a chave junto: `data_tests:` vazio é nulo, e o dbt recusa (RVB5A-1-01).
                ini, fim, recuo = _item_da_coluna(linhas, modelo, coluna)
                idx_t, fim_t = _subchave(linhas, ini + 1, fim, recuo + 2, "data_tests")
                if idx_t is not None and not _itens_da_lista(linhas, idx_t, fim_t):
                    del linhas[idx_t]
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
            if "data_tests" in c and not isinstance(c["data_tests"], list):
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}`: `data_tests` não é uma lista")
            if (c.get("meta") or {}).get("values") != pedido["values"]:
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}` não ficou com o `meta.values` do catálogo")
            testes = c.get("data_tests") or []
            av = [t for t in testes if _marcado(t, "accepted_values")]
            if len(av) != 1 or (av[0]["accepted_values"].get("arguments") or {}).get("values") != pedido["accepted"]:
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}` não ficou com o `accepted_values` do catálogo")
            derivados = sum(1 for t in testes if _marcado(t, "not_null"))
            a_mao = _not_null_a_mao(testes)
            if pedido["not_null"] and _not_null_a_mao_desligado(testes):
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}`: `not_null` à mão desligado, e a ligação exige `not_null`")
            if pedido["not_null"] != (a_mao or derivados == 1) or derivados > (0 if a_mao else 1) or (a_mao and derivados):
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}`: `not_null` diverge da ligação")
    for modelo, colunas in (remocoes or {}).items():
        cols = {c["name"]: c for c in (por_nome.get(modelo) or {}).get("columns", [])}
        for coluna in colunas:
            c = cols.get(coluna) or {}
            if "data_tests" in c and (not isinstance(c["data_tests"], list) or not c["data_tests"]):
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}`: `data_tests` sem lista depois da remoção")
            if "values" in (c.get("meta") or {}) or any(_marcado(t) for t in c.get("data_tests") or []):
                raise RuntimeError(f"{caminho.name}: `{modelo}.{coluna}` ainda tem o derivado de uma ligação que saiu")
