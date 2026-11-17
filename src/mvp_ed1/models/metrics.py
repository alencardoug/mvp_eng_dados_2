"""O montador fixo das métricas (ADR-0055; Bloco 5, Parte B, do plano da base dos consumidores).

Monta o SQL de cada view **só** a partir de `docs/glossario_de_negocio/metricas.yml`, para o teste o comparar
com a view auditada, linha a linha. A forma é uma só, e o ADR a descreve:

1. para cada fonte da view: ``select <grão da fonte>, <medidas> from <fonte> <junções> where <filtros>
   group by <grão da fonte>`` — a data liga a fato a `dim_date` (`d`), e só entram as junções que a view
   usa, com as de que elas dependem;
2. as fontes combinadas pela regra declarada (`full` ou `left`, pelas colunas de `keys`), com o valor de
   `missing` no lado ausente; a fonte de grão mais curto se repete em cada linha do grão mais longo;
3. as métricas por cima, sobre os nomes das medidas: a razão (`cast(<escala> as numeric) * num /
   nullif(den, 0)`, arredondada) e a diferença.

Nenhuma regra de negócio vive aqui: o filtro, a data, o grão, a fórmula, a escala e o arredondamento são da
declaração. O que não cabe nesta forma não se monta: a coluna aponta para a referência do Bloco 1b.
"""

from __future__ import annotations

import pathlib
import re

import yaml

from mvp_ed1.models import sensitivity

CATALOG_RELATIVE = pathlib.Path("docs") / "glossario_de_negocio" / "metricas.yml"
CATALOG = sensitivity.ROOT / CATALOG_RELATIVE
ROLES = ("grain", "identity", "measure", "metric", "reference")
AGGREGATES = ("sum", "count", "count_distinct", "count_where", "avg", "max", "median")


def load_catalog(caminho: pathlib.Path = CATALOG, conteudo: str | None = None) -> dict:
    """O catálogo, lido estrito (chave repetida é erro) e conferido nas referências entre as seções."""
    texto = caminho.read_text(encoding="utf-8") if conteudo is None else conteudo
    # O carregador estrito do catálogo dos `.yml` (chave repetida é erro), sem a leitura de `sources` do dbt.
    doc = yaml.load(texto, Loader=sensitivity._SemChaveRepetida) or {}
    for secao in ("sources", "filters", "measures", "metrics", "views"):
        if not isinstance(doc.get(secao), dict):
            raise ValueError(f"{caminho}: sem `{secao}`")
    # `on:` no YAML 1.1 é o booleano `True`: a junção e a combinação usam `match` e `keys`.
    for nome, fonte in doc["sources"].items():
        if any(True in j for j in fonte.get("joins") or []):
            raise ValueError(f"{caminho}: fonte `{nome}`: `on` vira booleano no YAML — escreva `match`")
    for nome, view in doc["views"].items():
        if True in (view.get("combine") or {}):
            raise ValueError(f"{caminho}: view `{nome}`: `on` vira booleano no YAML — escreva `keys`")
    for nome, filtro in doc["filters"].items():
        if filtro.get("source") not in doc["sources"]:
            raise ValueError(f"{caminho}: filtro `{nome}` cita a fonte `{filtro.get('source')}`, que não existe")
        if not filtro.get("predicate") or not filtro.get("label"):
            raise ValueError(f"{caminho}: filtro `{nome}` sem `predicate` e `label`")
    for nome, medida in doc["measures"].items():
        if medida.get("source") not in doc["sources"]:
            raise ValueError(f"{caminho}: medida `{nome}` cita a fonte `{medida.get('source')}`, que não existe")
        if medida.get("aggregate") not in AGGREGATES:
            raise ValueError(f"{caminho}: medida `{nome}`: `aggregate` é um de {AGGREGATES}")
        if medida["aggregate"] == "count_distinct" and not medida.get("identity"):
            raise ValueError(f"{caminho}: medida `{nome}`: contagem distinta sem `identity`")
        if medida["aggregate"] in ("sum", "avg", "max", "median") and not medida.get("expression"):
            raise ValueError(f"{caminho}: medida `{nome}`: `{medida['aggregate']}` sem `expression`")
        if medida["aggregate"] == "count_where" and not medida.get("where"):
            raise ValueError(f"{caminho}: medida `{nome}`: contagem condicional sem `where`")
        if medida.get("cast") not in (None, "numeric"):
            raise ValueError(f"{caminho}: medida `{nome}`: `cast` só é `numeric`")
        if medida.get("additivity") not in ("additive", "semi_additive", "non_additive"):
            raise ValueError(f"{caminho}: medida `{nome}` sem `additivity`")
        for f in medida.get("filters") or []:
            if f not in doc["filters"] or doc["filters"][f]["source"] != medida["source"]:
                raise ValueError(f"{caminho}: medida `{nome}`: o filtro `{f}` não é da fonte dela")
    for nome, metrica in doc["metrics"].items():
        partes = {"ratio": ("numerator", "denominator"), "difference": ("minuend", "subtrahend")}.get(metrica.get("kind"))
        if partes is None:
            raise ValueError(f"{caminho}: métrica `{nome}`: `kind` é `ratio` ou `difference`")
        for parte in partes:
            if metrica.get(parte) not in doc["measures"] and metrica.get(parte) not in doc["metrics"]:
                raise ValueError(f"{caminho}: métrica `{nome}`: `{parte}` não é medida nem métrica")
        if metrica["kind"] == "ratio" and metrica.get("on_zero_denominator") != "returns_null":
            raise ValueError(f"{caminho}: métrica `{nome}`: o denominador zero dá nulo (`on_zero_denominator: returns_null`)")
        if "zero_denominator" in metrica:
            raise ValueError(f"{caminho}: métrica `{nome}`: `zero_denominator` saiu da declaração; é `on_zero_denominator` (Q61)")
    for nome, view in doc["views"].items():
        _conferir_view(caminho, doc, nome, view)
    # O conceito do glossário e as medidas e métricas que ele explica (Q31): a regra vira trecho gerado no `.md`.
    if not isinstance(doc.get("concepts"), dict) or not doc["concepts"]:
        raise ValueError(f"{caminho}: sem `concepts`")
    for arquivo, nomes in doc["concepts"].items():
        if not (CATALOG.parent / arquivo).is_file():
            raise ValueError(f"{caminho}: conceito `{arquivo}`, que não existe no glossário")
        if not isinstance(nomes, list) or not nomes:
            raise ValueError(f"{caminho}: conceito `{arquivo}` sem medidas nem métricas")
        for n in nomes:
            if n not in doc["measures"] and n not in doc["metrics"]:
                raise ValueError(f"{caminho}: conceito `{arquivo}` cita `{n}`, que não é medida nem métrica")
    return doc


def _conferir_view(caminho, doc, nome, view) -> None:
    if "reference" in view:
        _conferir_referencia(caminho, nome, view)
        return
    fontes = view.get("sources") or []
    if not fontes or not view.get("grain") or not view.get("columns"):
        raise ValueError(f"{caminho}: view `{nome}` sem `grain`, `sources` ou `columns`")
    for f in fontes:
        if f["source"] not in doc["sources"]:
            raise ValueError(f"{caminho}: view `{nome}` cita a fonte `{f['source']}`, que não existe")
        if fora := sorted(set(f.get("grain") or []) - set(view["grain"])):
            raise ValueError(f"{caminho}: view `{nome}`: o grão da fonte `{f['source']}` tem {fora}, fora do grão da view")
    if len(fontes) > 1:
        combina = view.get("combine") or {}
        if combina.get("type") not in ("full", "left") or not combina.get("keys"):
            raise ValueError(f"{caminho}: view `{nome}` com duas fontes e sem `combine` (`full` ou `left`, `keys`)")
        if len(fontes) != 2:
            raise ValueError(f"{caminho}: view `{nome}`: o montador combina duas fontes")
    elif view.get("combine"):
        raise ValueError(f"{caminho}: view `{nome}` com uma fonte e `combine`: só duas fontes se combinam")
    for coluna, papel in view["columns"].items():
        papel_nome, alvo = role(coluna, papel)
        if papel_nome not in ROLES:
            raise ValueError(f"{caminho}: view `{nome}`, coluna `{coluna}`: papel `{papel_nome}` não é um de {ROLES}")
        if papel_nome == "grain" and coluna not in view["grain"]:
            raise ValueError(f"{caminho}: view `{nome}`, coluna `{coluna}`: grão sem expressão em `grain`")
        if papel_nome == "measure" and alvo not in doc["measures"]:
            raise ValueError(f"{caminho}: view `{nome}`, coluna `{coluna}`: medida `{alvo}` não declarada")
        if papel_nome == "metric" and alvo not in doc["metrics"]:
            raise ValueError(f"{caminho}: view `{nome}`, coluna `{coluna}`: métrica `{alvo}` não declarada")
        if isinstance(papel, dict) and papel.get("additivity") not in (None, *ADDITIVITY):
            raise ValueError(f"{caminho}: view `{nome}`, coluna `{coluna}`: `additivity` é um de {ADDITIVITY}")
    if faltam := sorted(set(view["grain"]) - set(view["columns"])):
        raise ValueError(f"{caminho}: view `{nome}`: grão {faltam} sem coluna")
    if "reference" in {role(c, p)[0] for c, p in view["columns"].items()}:
        raise ValueError(f"{caminho}: view `{nome}`: coluna `reference` numa view montada — a view inteira aponta para a referência")


def _conferir_referencia(caminho, nome, view) -> None:
    """A view que não cabe na forma: o teste e a consulta do Bloco 1b que a conferem, com o motivo."""
    ref = view["reference"]
    if not isinstance(ref, dict) or not ref.get("test") or not ref.get("query") or not ref.get("reason"):
        raise ValueError(f"{caminho}: view `{nome}`: `reference` com `test`, `query` e `reason`")
    if not view.get("columns"):
        raise ValueError(f"{caminho}: view `{nome}` sem `columns`")
    for coluna, papel in view["columns"].items():
        papel_nome = role(coluna, papel)[0]
        if papel_nome not in ("grain", "identity", "reference"):
            raise ValueError(f"{caminho}: view `{nome}`, coluna `{coluna}`: numa view por referência, o papel é `grain`, `identity` ou `reference`")
        if papel_nome == "reference" and (not isinstance(papel, dict) or papel["reference"] not in ADDITIVITY):
            raise ValueError(f"{caminho}: view `{nome}`, coluna `{coluna}`: `reference` leva a aditividade ({ADDITIVITY})")
    if not view.get("facts") or not view.get("dimensions"):
        raise ValueError(f"{caminho}: view `{nome}`: a view por referência declara `facts` e `dimensions`")
    if view.get("sources") or view.get("grain"):
        raise ValueError(f"{caminho}: view `{nome}`: `reference` não se monta — tire `sources` e `grain`")


ADDITIVITY = ("additive", "semi_additive", "non_additive")
PAPEL_CHAVES = {"additivity", "note"}


def role(coluna: str, papel) -> tuple[str, str]:
    """(papel, nome declarado): `measure` é a medida do mesmo nome; `{measure: x}`, a medida `x`; a coluna pode
    trazer `additivity` (quando o grão da view muda a da medida) e `note`. Na view por referência,
    `{reference: <aditividade>}`."""
    if isinstance(papel, str):
        return papel, coluna
    nomes = [k for k in papel if k in ROLES]
    if len(nomes) != 1 or set(papel) - set(nomes) - PAPEL_CHAVES:
        raise ValueError(f"coluna `{coluna}`: papel {papel!r} fora da forma")
    nome = nomes[0]
    alvo = papel[nome]
    return nome, (alvo if nome != "reference" and isinstance(alvo, str) else coluna)


def additivity(doc: dict, view: dict, coluna: str) -> str:
    """A aditividade da coluna na view: a declarada nela, a da referência, a da medida, ou a da métrica."""
    papel = view["columns"][coluna]
    nome, alvo = role(coluna, papel)
    if isinstance(papel, dict) and papel.get("additivity"):
        return papel["additivity"]
    if nome == "reference":
        return papel["reference"] if isinstance(papel, dict) else None
    if nome == "measure":
        return doc["measures"][alvo]["additivity"]
    if nome == "metric":
        return _aditividade_da_metrica(doc, alvo)
    return None


def _aditividade_da_metrica(doc: dict, nome: str) -> str:
    if nome in doc["measures"]:
        return doc["measures"][nome]["additivity"]
    m = doc["metrics"][nome]
    if m["kind"] == "ratio":
        return "non_additive"
    partes = {_aditividade_da_metrica(doc, m["minuend"]), _aditividade_da_metrica(doc, m["subtrahend"])}
    return "additive" if partes == {"additive"} else "non_additive"


def note(doc: dict, view: dict, coluna: str) -> str | None:
    papel = view["columns"][coluna]
    nome, alvo = role(coluna, papel)
    if isinstance(papel, dict) and papel.get("note"):
        return papel["note"]
    return doc["measures"][alvo].get("note") if nome == "measure" else None


# ── A montagem ──────────────────────────────────────────────────────────────────────

_APELIDO = re.compile(r"\b([a-z_][a-z0-9_]*)\.[a-z_]")


def _apelidos(texto: str) -> set[str]:
    return set(_APELIDO.findall(texto))


def _medidas_da_fonte(doc: dict, view: dict, fonte: dict) -> list[str]:
    """As medidas que a fonte agrega nesta view: as declaradas nela, ou todas as da view desta fonte."""
    if fonte.get("measures"):
        return list(fonte["measures"])
    usadas = _medidas_usadas(doc, view)
    return [m for m in usadas if doc["measures"][m]["source"] == fonte["source"]]


def _medidas_usadas(doc: dict, view: dict) -> list[str]:
    saida: list[str] = []

    def visitar(nome: str) -> None:
        if nome in doc["measures"]:
            if nome not in saida:
                saida.append(nome)
            return
        metrica = doc["metrics"][nome]
        for parte in ("numerator", "denominator", "minuend", "subtrahend"):
            if parte in metrica:
                visitar(metrica[parte])

    for coluna, papel in view["columns"].items():
        papel_nome, alvo = role(coluna, papel)
        if papel_nome in ("measure", "metric"):
            visitar(alvo)
    return saida


def _agregado(medida: dict) -> str:
    """O agregado da medida: a função, a condição da própria medida (`where`), o `cast` e o `round`, nesta ordem."""
    tipo = medida["aggregate"]
    if tipo == "count_distinct":
        identidade = medida["identity"]
        sql = f"count(distinct ({', '.join(identidade)}))" if len(identidade) > 1 else f"count(distinct {identidade[0]})"
    elif tipo in ("count", "count_where"):
        sql = "count(*)"
    elif tipo == "median":
        sql = f"percentile_cont(0.5) within group (order by {medida['expression']})"
    else:
        sql = f"{tipo}({medida['expression']})"
    if medida.get("where"):
        sql = f"{sql} filter (where {medida['where']})"
    if medida.get("cast"):
        sql = f"cast({sql} as {medida['cast']})"
    if medida.get("round") is not None:
        sql = f"round({sql}, {medida['round']})"
    return sql


def _cte_da_fonte(doc: dict, view: dict, fonte: dict) -> tuple[str, list[str], list[str]]:
    """(SQL, grão, medidas) da agregação de uma fonte no grão dela."""
    declarada = doc["sources"][fonte["source"]]
    grao = list(fonte.get("grain") or view["grain"])
    medidas = _medidas_da_fonte(doc, view, fonte)
    filtros = []
    for m in medidas:
        for f in doc["measures"][m].get("filters") or []:
            if f not in filtros:
                filtros.append(f)
    # Medidas da mesma fonte com filtros diferentes não cabem num `where` só: fora da forma.
    conjuntos = {tuple(doc["measures"][m].get("filters") or []) for m in medidas}
    if len(conjuntos) > 1:
        raise ValueError(f"fonte `{fonte['source']}`: as medidas têm filtros diferentes ({sorted(conjuntos)})")
    selecao = [f"{view['grain'][g]} as {g}" for g in grao] + [f"{_agregado(doc['measures'][m])} as {m}" for m in medidas]
    usados = set().union(*(_apelidos(view["grain"][g]) for g in grao),
                         *(_apelidos(_agregado(doc["measures"][m])) for m in medidas),
                         *(_apelidos(doc["filters"][f]["predicate"]) for f in filtros))
    juncoes = declarada.get("joins") or []
    incluir = _juncoes_incluidas(juncoes, usados)
    base = declarada["alias"]
    linhas = [f"select {', '.join(selecao)}", f"from {declarada['relation']} {base}"]
    if "d" in usados:
        linhas.append(f"join analytics.dim_date d on d.date_key = {base}.{declarada['date']['column']}")
    for j in juncoes:  # na ordem declarada
        if j["alias"] not in incluir:
            continue
        if j.get("using"):
            linhas.append(f"join {j['relation']} {j['alias']} using ({', '.join(j['using'])})")
        else:
            linhas.append(f"join {j['relation']} {j['alias']} on " + " and ".join(f"{a} = {b}" for a, b in j["match"]))
    if filtros:
        linhas.append("where " + " and ".join(f"({doc['filters'][f]['predicate']})" for f in filtros))
    linhas.append("group by " + ", ".join(str(i + 1) for i in range(len(grao))))
    return "\n".join(linhas), grao, medidas


def _juncoes_incluidas(juncoes: list[dict], usados: set[str]) -> set[str]:
    """Os apelidos das junções que a view usa, com as de que elas dependem pelo `match`."""
    incluir: set[str] = set()
    pendentes = [j for j in juncoes if j["alias"] in usados]
    while pendentes:
        j = pendentes.pop()
        if j["alias"] in incluir:
            continue
        incluir.add(j["alias"])
        for par in j.get("match") or []:
            for apelido in _apelidos(" ".join(par)):
                pendentes += [k for k in juncoes if k["alias"] == apelido and k["alias"] not in incluir]
    return incluir


def relations(doc: dict, nome_da_view: str) -> tuple[list[str], list[str]]:
    """(fatos, dimensões) de `analytics` que a view lê: das fontes e das junções que a montagem usa, ou os
    declarados na view por referência. O teste os confere contra o `depends_on` do *manifest*."""
    view = doc["views"][nome_da_view]
    if "reference" in view:
        return list(view["facts"]), list(view["dimensions"])
    fatos, dims = [], []
    for fonte in view["sources"]:
        declarada = doc["sources"][fonte["source"]]
        sql = _cte_da_fonte(doc, view, fonte)[0]
        if declarada["relation"] not in fatos:
            fatos.append(declarada["relation"])
        if "join analytics.dim_date d " in sql and "analytics.dim_date" not in dims:
            dims.append("analytics.dim_date")
        for j in declarada.get("joins") or []:
            if f"join {j['relation']} {j['alias']} " in sql and j["relation"] not in dims:
                dims.append(j["relation"])
    return fatos, dims


ROTULO = {"additive": "aditiva", "semi_additive": "**semiaditiva**", "non_additive": "**não aditiva**"}


def question_table(doc: dict, nome_da_view: str) -> str:
    """A tabela Fatos · Medidas · Dimensões · View da pergunta, gerada da declaração (F23)."""
    view = doc["views"][nome_da_view]
    fatos, dims = relations(doc, nome_da_view)
    curto = lambda r: f"`{r.split('.', 1)[1]}`"
    fato = " · ".join(curto(f) for f in fatos) + (f" — {view['facts_note']}" if view.get("facts_note") else "")
    medidas = []
    for coluna, papel in view["columns"].items():
        if role(coluna, papel)[0] in ("measure", "metric", "reference"):
            n = note(doc, view, coluna)
            medidas.append(f"`{coluna}` ({ROTULO[additivity(doc, view, coluna)]}{' — ' + n if n else ''})")
    return "\n".join([
        "| | |", "|---|---|",
        f"| **{'Fato' if len(fatos) == 1 else 'Fatos'}** | {fato} |",
        f"| **Medidas** | {' · '.join(medidas)} |",
        f"| **Dimensões** | {' · '.join(curto(d) for d in dims)} |",
        f"| **View** | `{nome_da_view}` |",
    ])


def question_tables(doc: dict | None = None) -> list[str]:
    """Os 16 trechos das perguntas, na ordem P01 a P16: a tabela e, abaixo dela, a regra (Q32)."""
    doc = load_catalog() if doc is None else doc
    por_pergunta = {v["question"]: n for n, v in doc["views"].items()}
    return [f"{question_table(doc, n)}\n\n{question_rule(doc, n)}"
            for n in (por_pergunta[f"P{i:02d}"] for i in range(1, 17))]


def view_rules(doc: dict | None = None) -> dict:
    """`view_rules` do pacote (Q33; RVB5B-1-02): a montagem de cada view, como a declaração a diz — o grão, as
    fontes com o grão, as medidas, os filtros e as junções que a montagem usa, a combinação e o papel de cada
    coluna; na view por referência, o teste, a consulta e o motivo. Toda chave presente; `null` onde não se aplica."""
    doc = load_catalog() if doc is None else doc
    saida = {}
    for nome, view in doc["views"].items():
        fatos, dims = relations(doc, nome)
        fontes = []
        for fonte in view.get("sources") or []:
            declarada = doc["sources"][fonte["source"]]
            sql, grao, medidas = _cte_da_fonte(doc, view, fonte)
            filtros: list[str] = []
            for m in medidas:
                filtros += [f for f in doc["measures"][m].get("filters") or [] if f not in filtros]
            fontes.append({
                "relation": declarada["relation"], "alias": declarada["alias"],
                "date": {"column": declarada["date"]["column"], "label": declarada["date"]["label"]},
                "grain": list(grao), "measures": list(medidas), "filters": filtros,
                "joins": [j["relation"] for j in declarada.get("joins") or []
                          if f"join {j['relation']} {j['alias']} " in sql],
            })
        combina = view.get("combine")
        colunas = {}
        for coluna, papel in view["columns"].items():
            papel_nome, alvo = role(coluna, papel)
            colunas[coluna] = {
                "role": papel_nome,
                "name": alvo if papel_nome in ("measure", "metric") else None,
                "additivity": additivity(doc, view, coluna) if papel_nome in ("measure", "metric", "reference") else None,
                "note": note(doc, view, coluna),
            }
        ref = view.get("reference")
        saida[f"consumption.{nome}"] = {
            "question": view["question"], "facts": fatos, "dimensions": dims,
            "grain": dict(view["grain"]) if view.get("grain") else None,
            "sources": fontes,
            "combine": {"type": combina["type"], "keys": list(combina["keys"]), "missing": combina.get("missing")}
                       if combina else None,
            "columns": colunas,
            "reference": {"test": ref["test"], "query": ref["query"], "reason": ref["reason"]} if ref else None,
        }
    return saida


# ── Os trechos de regra (entrega 4; Q30 a Q32) ────────────────────────────────────
#
# A regra sai da declaração como texto; nenhuma regra nova nasce aqui. O texto curto do BigQuery não
# muda: no conceito, o trecho fica depois da marca (Q30).

FONTE = "`docs/glossario_de_negocio/metricas.yml`"
_ROTULO_FRASE = {"additive": "Aditiva", "semi_additive": "Semiaditiva", "non_additive": "Não aditiva"}
_FUNCAO = {"sum": "soma de", "avg": "média de", "max": "máximo de", "median": "mediana de"}


def _pela(rotulo: str) -> str:
    """'a data do pedido' → 'pela data do pedido'."""
    artigo, _, resto = rotulo.partition(" ")
    return {"a": "pela", "o": "pelo"}.get(artigo, "por " + artigo) + " " + resto


def _rotulos(doc: dict, filtros: list[str]) -> str:
    return " ".join(doc["filters"][f]["label"] for f in filtros)


def _conta(m: dict) -> str:
    """O agregado da medida em texto: a função, a condição própria (`where`) e o arredondamento."""
    tipo = m["aggregate"]
    if tipo == "count_distinct":
        partes = [f"`{x}`" for x in m["identity"]]
        conta = f"contagem distinta de {partes[0]}" if len(partes) == 1 else f"contagem distinta de ({', '.join(partes)})"
    elif tipo == "count":
        conta = "contagem das linhas"
    elif tipo == "count_where":
        conta = f"contagem das linhas com `{m['where']}`"
    else:
        conta = f"{_FUNCAO[tipo]} `{m['expression']}`"
    if m.get("where") and tipo != "count_where":
        conta += f", só onde `{m['where']}`"
    if m.get("round") is not None:
        conta += f", arredondada a {m['round']} casas"
    return conta


def _frase_da_medida(doc: dict, nome: str) -> str:
    m = doc["measures"][nome]
    fonte = doc["sources"][m["source"]]
    frase = f"`{nome}`: {_conta(m)}, em `{fonte['relation']}`, {_pela(fonte['date']['label'])}."
    if m.get("filters"):
        frase += " " + _rotulos(doc, m["filters"])
    return f"{frase} {_ROTULO_FRASE[m['additivity']]}."


def _frase_da_metrica(doc: dict, nome: str) -> str:
    m = doc["metrics"][nome]
    if m["kind"] == "difference":
        return f"`{nome}` = `{m['minuend']}` − `{m['subtrahend']}`. {_ROTULO_FRASE[_aditividade_da_metrica(doc, nome)]}."
    escala = f"{m['scale']} × " if m.get("scale") else ""
    casas = f", arredondada a {m['round']} casas" if m.get("round") is not None else ""
    return f"`{nome}` = {escala}`{m['numerator']}` ÷ `{m['denominator']}`{casas}; nula com o denominador zero. Não aditiva."


def _com_as_partes(doc: dict, nomes: list[str]) -> list[str]:
    """Os nomes com as partes de cada métrica antes dela, sem repetir."""
    saida: list[str] = []

    def visitar(nome: str) -> None:
        if nome in saida:
            return
        for parte in ("numerator", "denominator", "minuend", "subtrahend"):
            if (doc["metrics"].get(nome) or {}).get(parte):
                visitar(doc["metrics"][nome][parte])
        saida.append(nome)

    for n in nomes:
        visitar(n)
    return saida


def concept_rule(doc: dict, arquivo: str) -> str:
    """A regra das medidas e métricas que a seção `concepts:` liga ao conceito (Q31), uma por linha."""
    linhas = [f"**Como as views o contam** (gerado de {FONTE}; a definição e o porquê ficam no texto acima):", ""]
    for nome in _com_as_partes(doc, doc["concepts"][arquivo]):
        linhas.append("- " + (_frase_da_metrica(doc, nome) if nome in doc["metrics"] else _frase_da_medida(doc, nome)))
    return "\n".join(linhas)


def question_rule(doc: dict, nome_da_view: str) -> str:
    """Como a view se monta, em texto (Q32): cada fonte com a data e os filtros, a combinação e as métricas."""
    view = doc["views"][nome_da_view]
    if "reference" in view:
        ref = view["reference"]
        return (f"**Conferida por referência** (gerado de {FONTE}): `{ref['test']}`, contra `{ref['query']}`. "
                f"{ref['reason']}")
    linhas = [f"**Como se monta** (gerado de {FONTE}):", ""]
    for fonte in view["sources"]:
        declarada = doc["sources"][fonte["source"]]
        filtros: list[str] = []
        for m in _medidas_da_fonte(doc, view, fonte):
            filtros += [f for f in doc["measures"][m].get("filters") or [] if f not in filtros]
        frase = f"- `{declarada['relation']}`, {_pela(declarada['date']['label'])}."
        frase += " " + (_rotulos(doc, filtros) if filtros else "Sem filtro.")
        # A junção composta muda o número (a categoria do CMV pelo produto e pela origem, P08): ela aparece; a
        # junção pela chave substituta, não. Só a que a montagem desta view usa.
        sql = _cte_da_fonte(doc, view, fonte)[0]
        for j in declarada.get("joins") or []:
            if j.get("match") and f"join {j['relation']} {j['alias']} on " in sql:
                frase += (f" Liga `{j['relation']}` por "
                          + " e ".join(f"`{x} = {y}`" for x, y in j["match"]) + ".")
        if fonte.get("grain"):
            frase += (" Agregada só por " + ", ".join(f"`{g}`" for g in fonte["grain"])
                      + ": o valor se repete em cada linha do grão da view que casa com ela.")
        linhas.append(frase)
    if combina := view.get("combine"):
        chaves = " e ".join(f"`{k}`" for k in combina["keys"])
        ausente = "nulo" if combina.get("missing") is None else f"`{combina['missing']}`"
        if combina["type"] == "full":
            linhas.append(f"- As duas fontes se combinam por {chaves}: a linha de um lado só aparece, com {ausente} no lado ausente.")
        else:
            linhas.append(f"- As duas fontes se combinam por {chaves}: toda linha da primeira fica; sem par, a segunda fica com {ausente}.")
    for coluna, papel in view["columns"].items():
        papel_nome, alvo = role(coluna, papel)
        if papel_nome == "measure":
            linhas.append(f"- `{coluna}`: {_conta(doc['measures'][alvo])}.")
        elif papel_nome == "metric":
            linhas.append("- " + _frase_da_metrica(doc, alvo))
    return "\n".join(linhas)


# ── O que o pacote publica (Bloco 5, item 10) ───────────────────────────────────────

#: O glossário, relativo a `provenance.link_base` (`docs/`): o `concept` do filtro é um link.
GLOSSARIO = "glossario_de_negocio/"


def _fonte_publicada(fonte: dict) -> dict:
    """A fonte como as expressões a leem: a relação, o apelido, a data e as junções, na ordem declarada."""
    return {
        "relation": fonte["relation"], "alias": fonte["alias"],
        "date": {"column": fonte["date"]["column"], "label": fonte["date"]["label"]},
        "joins": [{"relation": j["relation"], "alias": j["alias"], "using": j.get("using"), "match": j.get("match")}
                  for j in fonte.get("joins") or []],
    }


def package_fields(doc: dict | None = None) -> tuple[dict, dict]:
    """(`metrics`, `filters`) do pacote: a declaração, sem regra nova; toda chave presente, `null` onde não se aplica.

    `metrics` tem uma entrada por medida (`kind: measure`) e por métrica (`ratio`, `difference`), com a fonte
    resolvida e as colunas das views montadas que a publicam (`columns`), cada uma com a aditividade dela."""
    doc = load_catalog() if doc is None else doc
    filtros = {nome: {"relation": doc["sources"][f["source"]]["relation"], "predicate": f["predicate"],
                      "label": f["label"], "concept": GLOSSARIO + f["concept"]}
               for nome, f in doc["filters"].items()}
    publicada: dict[str, list[dict]] = {n: [] for n in (*doc["measures"], *doc["metrics"])}
    for nome_view, view in doc["views"].items():
        if "reference" in view:
            continue
        for coluna, papel in view["columns"].items():
            papel_nome, alvo = role(coluna, papel)
            if papel_nome in ("measure", "metric"):
                # A aditividade é a da coluna na view: o grão pode mudá-la (a `order_count` por categoria, F28).
                publicada[alvo].append({"column": f"consumption.{nome_view}.{coluna}",
                                        "additivity": additivity(doc, view, coluna)})
    vazio = dict.fromkeys(("source", "aggregate", "expression", "identity", "where", "filters", "cast",
                           "numerator", "denominator", "minuend", "subtrahend", "scale", "round", "zero_denominator",
                           "on_zero_denominator"))
    saida = {}
    for nome, m in doc["measures"].items():
        saida[nome] = {**vazio, "kind": "measure", "additivity": m["additivity"], "note": m.get("note"),
                       "source": _fonte_publicada(doc["sources"][m["source"]]), "aggregate": m["aggregate"],
                       "expression": m.get("expression"), "identity": m.get("identity"), "where": m.get("where"),
                       "filters": list(m.get("filters") or []), "cast": m.get("cast"), "round": m.get("round")}
    for nome, m in doc["metrics"].items():
        saida[nome] = {**vazio, "kind": m["kind"], "additivity": _aditividade_da_metrica(doc, nome), "note": None,
                       **{k: m.get(k) for k in ("numerator", "denominator", "minuend", "subtrahend", "scale", "round",
                                                "on_zero_denominator")},
                       # O campo antigo, só por compatibilidade com o formato 1 (Q61): o texto `"null"` dizia o
                       # mesmo que `returns_null`, e se confundia com o `null` de "não se aplica".
                       "zero_denominator": "null" if m.get("on_zero_denominator") == "returns_null" else None}
    for nome, entrada in saida.items():
        entrada["columns"] = sorted(publicada[nome], key=lambda x: x["column"])
    return saida, filtros


def _expressao(doc: dict, nome: str) -> str:
    """A expressão de uma medida ou métrica sobre as colunas da combinação."""
    if nome in doc["measures"]:
        return nome
    m = doc["metrics"][nome]
    if m["kind"] == "difference":
        return f"({_expressao(doc, m['minuend'])} - {_expressao(doc, m['subtrahend'])})"
    escala = m.get("scale")
    numerador = _expressao(doc, m["numerator"])
    corpo = f"cast({float(escala)} as numeric) * {numerador}" if escala is not None else f"cast({numerador} as numeric)"
    corpo = f"{corpo} / nullif({_expressao(doc, m['denominator'])}, 0)"
    return f"round({corpo}, {m['round']})" if m.get("round") is not None else corpo


def assemble(doc: dict, nome_da_view: str) -> str:
    """O SQL da view, montado só da declaração; as colunas saem na ordem e com os nomes da view."""
    view = doc["views"][nome_da_view]
    if "reference" in view:
        raise ValueError(f"`{nome_da_view}` é conferida por referência ({view['reference']['query']}), não se monta")
    ctes, partes = [], []
    for i, fonte in enumerate(view["sources"]):
        sql, grao, medidas = _cte_da_fonte(doc, view, fonte)
        ctes.append(f"s{i} as (\n{sql}\n)")
        partes.append((f"s{i}", grao, medidas))
    if len(partes) == 1:
        apelido, grao, medidas = partes[0]
        combinacao = f"select * from {apelido}"
    else:
        combina = view["combine"]
        (a, grao_a, med_a), (b, grao_b, med_b) = partes
        tipo = "full outer join" if combina["type"] == "full" else "left join"
        falta = combina.get("missing")
        colunas = []
        for g in view["grain"]:
            if combina["type"] == "full" and g in grao_a and g in grao_b:
                colunas.append(f"coalesce({a}.{g}, {b}.{g}) as {g}")
            else:
                colunas.append(f"{a if g in grao_a else b}.{g} as {g}")
        for apelido, medidas in ((a, med_a), (b, med_b)):
            for m in medidas:
                colunas.append(f"coalesce({apelido}.{m}, {falta}) as {m}" if falta is not None else f"{apelido}.{m} as {m}")
        juncao = " and ".join(f"{b}.{c} = {a}.{c}" for c in combina["keys"])
        combinacao = f"select {', '.join(colunas)}\nfrom {a}\n{tipo} {b} on {juncao}"
    ctes.append(f"combinada as (\n{combinacao}\n)")
    final = []
    for coluna, papel in view["columns"].items():
        papel_nome, alvo = role(coluna, papel)
        if papel_nome == "grain":
            final.append(coluna)
        elif papel_nome == "measure":
            final.append(f"{alvo} as {coluna}")
        elif papel_nome == "metric":
            final.append(f"{_expressao(doc, alvo)} as {coluna}")
        else:
            raise ValueError(f"`{nome_da_view}.{coluna}`: papel `{papel}` não se monta")
    return "with " + ",\n".join(ctes) + f"\nselect {', '.join(final)}\nfrom combinada"
