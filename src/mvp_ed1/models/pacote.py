"""O pacote de metadados da D91, no formato 1 (`docs/pacote_de_metadados.md`).

Compõe o que os exportadores já dão, sem reimplementar a inferência: o *manifest* e o
`run_results.json` do dbt, o `lineage --json` (formato 1), as travessias, as Perguntas de
Negócio, o resultado declarado da auditoria das views, o relatório JUnit do `pytest` e os
itens em aberto das Pendências. Escreve `docs/pacote_de_metadados.json`, determinístico para
os mesmos artefatos, e recusa escrever pacote parcial: falta de artefato ou pacote que não
passa no esquema não escreve nada.

A guarda (RVG-1-04) é o `inputs_sha256`: o SHA-256 do conteúdo dos arquivos rastreados que
alimentam o pacote. O `check-offline` o recalcula sem nenhum artefato do dbt e recusa o
pacote atrasado (`tests/test_pacote_gerado.py`). O pacote não cita o *commit* que o contém.

O que o digest não alcança, porque está fora do Git, tem duas guardas (RVB4-1-01, RVB4-1-02):

* **o carimbo do *build*** — `make dbt-build` grava em `dbt/target/pacote_carimbo.json` o digest
  dos insumos do dbt lido **antes** do *build* e o `invocation_id` do *manifest* que ele produziu.
  O gerador recusa o *manifest* de outra execução ou de outros insumos: regerar sobre um
  *manifest* atrasado daria o digest novo a conteúdo velho;
* **a conferência do `make check`** (`--check`), depois do `pytest`: monta o pacote sem escrever e
  o compara com o versionado, sem os instantes e as execuções. Resultado de teste ou de `pytest`
  que mudou, teste novo ou sumido, descrição nova: o pacote está atrasado.

E nada parcial nem sensível sai: os leitores de Markdown recusam o que não reconhecem e conferem a
cobertura; o JUnit recusa módulo que não existe e identificador repetido; o pacote inteiro, chaves
inclusive, recusa caminho fora do repositório (regra 7); e cada instante passa pelo calendário.
"""

from __future__ import annotations

import ast
import copy
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import yaml

from mvp_ed1.models import lineage, sensitivity

ROOT = sensitivity.ROOT
DBT = sensitivity.DBT
MANIFEST = sensitivity.MANIFEST
RUN_RESULTS = DBT / "target" / "run_results.json"
CARIMBO = DBT / "target" / "pacote_carimbo.json"
JUNIT = ROOT / "data" / "pytest" / "junit.xml"
PACOTE = ROOT / "docs" / "pacote_de_metadados.json"
ESQUEMA = ROOT / "docs" / "pacote_de_metadados.schema.json"
PERGUNTAS = ROOT / "docs" / "glossario_de_negocio" / "perguntas_de_negocio.md"
RESULTADO = ROOT / "tests" / "auditoria" / "resultado.yml"
PENDENCIAS = ROOT / "docs" / "pendencias.md"
FORMATO = 1

#: O que alimenta o pacote, rastreado pelo Git. Mudar um destes muda o `inputs_sha256`.
INSUMOS = (
    "dbt/dbt_project.yml",
    "dbt/models/**/*.yml",
    "dbt/models/**/*.sql",
    "dbt/snapshots/*",
    "dbt/seeds/*",
    "dbt/macros/*.sql",
    "dbt/tests/*.sql",
    "docs/glossario_de_negocio/*.md",
    "docs/pendencias.md",
    "docs/adr/README.md",
    "tests/auditoria/resultado.yml",
    "airbyte/streams.yml",
    "streaming/fluxo.yml",
    "airflow/dags/fluxo_batch.py",
    "src/mvp_ed1/models/*.py",
    "src/mvp_ed1/legacy/ponte.py",
    "src/mvp_ed1/docs_check.py",        # o `slug` das âncoras de `open_items`
    "dbt/profiles.yml",                 # o `dbt_target` de `provenance.environment`
    "tests/**/test_*.py",               # o `summary` de `checks`: só a 1ª linha da docstring conta
)

#: Os insumos que o dbt lê para produzir o *manifest*: os que o carimbo do *build* fixa.
INSUMOS_DO_DBT = ("dbt/", "docs/glossario_de_negocio/")

#: A fonte da página de estrutura e ambientes, artefato por artefato (L4, L10).
AMBIENTES = [
    {"id": "compose_bancos", "title": "Bancos e serviços locais", "repository": "mvp_eng_dados_2", "path": "docker/docker-compose.yml", "delivery": "read_by_commit", "commit": None, "frozen_at": None, "note": None},
    {"id": "compose_airflow", "title": "Orquestração local", "repository": "mvp_eng_dados_2", "path": "docker/docker-compose.airflow.yml", "delivery": "read_by_commit", "commit": None, "frozen_at": None, "note": None},
    {"id": "compose_streaming", "title": "Streaming local", "repository": "mvp_eng_dados_2", "path": "docker/docker-compose.streaming.yml", "delivery": "read_by_commit", "commit": None, "frozen_at": None, "note": None},
    {"id": "terraform", "title": "Infraestrutura GCP declarada", "repository": "mvp_eng_dados_2", "path": "terraform/", "delivery": "read_by_commit", "commit": None, "frozen_at": "2026-11-13", "note": "Declaração; os recursos foram destruídos em 13/11/2026."},
    {"id": "mapa_de_paridade", "title": "Mapa de paridade local ↔ GCP", "repository": "mvp_eng_dados_2", "path": "docs/arquitetura.md#5-mapa-de-paridade-local--gcp", "delivery": "read_by_commit", "commit": None, "frozen_at": None, "note": None},
    {"id": "arquitetura", "title": "Arquitetura", "repository": "mvp_eng_dados_2", "path": "docs/arquitetura.md", "delivery": "read_by_commit", "commit": None, "frozen_at": None, "note": None},
    {"id": "modelo_de_dados", "title": "Modelo de dados", "repository": "mvp_eng_dados_2", "path": "docs/modelo_de_dados.md", "delivery": "read_by_commit", "commit": None, "frozen_at": None, "note": None},
    {"id": "registro_fase_gcp", "title": "Registro da fase GCP", "repository": "mvp_eng_dados_2", "path": "docs/registro_fase_gcp.md", "delivery": "read_by_commit", "commit": None, "frozen_at": "2026-11-13", "note": "Processo da Etapa 13; o custo real entra quando o faturamento fechar."},
    {"id": "evidencias_gcp", "title": "Evidências coletadas no GCP antes do desmonte", "repository": "mvp_eng_dados_1", "path": "data/medicoes/etapa_13/evidencias/", "delivery": "not_available", "commit": None, "frozen_at": "2026-11-13", "note": "Fora do Git (L10); se entram, e sanitizadas como, é decisão pendente."},
]

ADITIVIDADE = {"aditiva": "additive", "semiaditiva": "semi_additive", "não aditiva": "non_additive"}


# ── A guarda ────────────────────────────────────────────────────────────────────

def insumos(raiz: pathlib.Path = ROOT) -> list[str]:
    """Os arquivos rastreados que alimentam o pacote, em ordem."""
    rastreados = subprocess.run(["git", "ls-files", "-z"], cwd=raiz, capture_output=True, check=True).stdout.decode().split("\0")
    escolhidos = {p for p in rastreados if p and any(pathlib.PurePosixPath(p).match(g) or _casa(p, g) for g in INSUMOS)}
    return sorted(escolhidos)


def _casa(caminho: str, padrao: str) -> bool:
    if "**" not in padrao:
        return False
    prefixo, _, sufixo = padrao.partition("/**/")
    return caminho.startswith(prefixo + "/") and pathlib.PurePosixPath(caminho).match(sufixo)


def _modulo_de_teste(caminho: str) -> bool:
    return caminho.startswith("tests/") and pathlib.PurePosixPath(caminho).name.startswith("test_")


def _conteudo(raiz: pathlib.Path, caminho: str) -> bytes:
    """O que o pacote lê do insumo: o arquivo inteiro; do módulo de teste, só o `summary`."""
    if _modulo_de_teste(caminho):
        return (_resumo(raiz / caminho) or "").encode()
    return (raiz / caminho).read_bytes()


def digest(caminhos: list[str], raiz: pathlib.Path = ROOT, conteudo=None) -> str:
    """SHA-256 de `caminho\\0sha256(conteúdo)\\n` em ordem. `conteudo` troca a leitura (contraprovas)."""
    h = hashlib.sha256()
    for c in caminhos:
        dados = conteudo(c) if conteudo else _conteudo(raiz, c)
        h.update(c.encode() + b"\0" + hashlib.sha256(dados).hexdigest().encode() + b"\n")
    return h.hexdigest()


def digest_do_dbt(raiz: pathlib.Path = ROOT) -> str:
    """O digest dos insumos que o dbt lê — o que o carimbo do *build* fixa."""
    return digest([c for c in insumos(raiz) if c.startswith(INSUMOS_DO_DBT)], raiz)


def carimbar(digest_antes: str, inicio: str, manifest: pathlib.Path = MANIFEST, carimbo: pathlib.Path = CARIMBO) -> bool:
    """Depois do *build*: o *manifest* desta execução foi produzido destes insumos (lidos antes dela).

    Só carimba o *manifest* escrito **depois** de `inicio` (UTC, o instante em que o *build* começou):
    se o dbt falhou antes de escrevê-lo, o que está em `dbt/target` é o de outra execução, e carimbá-lo
    daria a ele os insumos de agora. Nesse caso o carimbo antigo sai, e o pacote recusa até o próximo
    *build* que escreva o *manifest*.
    """
    comeco = dt.datetime.fromisoformat(inicio)
    dado = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None
    if dado is None or dt.datetime.fromisoformat(dado["metadata"]["generated_at"]) < comeco:
        carimbo.unlink(missing_ok=True)
        print(f"aviso: o dbt não escreveu {manifest.name} nesta execução; sem carimbo, o pacote de metadados recusa "
              "até o próximo `make dbt-build`", file=sys.stderr)
        return False
    carimbo.write_text(json.dumps({"inputs_sha256_dbt": digest_antes,
                                   "manifest_invocation_id": dado["metadata"]["invocation_id"]}) + "\n", encoding="utf-8")
    return True


def conferir_carimbo(manifest: dict, atual: str, carimbo: pathlib.Path = CARIMBO) -> None:
    """Recusa o *manifest* que não é o do último `make dbt-build` sobre os insumos de agora (RVB4-1-02)."""
    if not carimbo.exists():
        raise SystemExit(f"sem {carimbo.name}: o *manifest* não veio de `make dbt-build`; rode-o — nenhum pacote é escrito")
    dado = json.loads(carimbo.read_text(encoding="utf-8"))
    if dado.get("manifest_invocation_id") != manifest["metadata"]["invocation_id"]:
        raise SystemExit("o *manifest* é de outra execução do dbt que não a do último `make dbt-build`; "
                         "rode `make dbt-build` — nenhum pacote é escrito")
    if dado.get("inputs_sha256_dbt") != atual:
        raise SystemExit("os insumos do dbt mudaram depois do último `make dbt-build` (o *manifest* está atrasado); "
                         "rode `make dbt-build` e `make catalog` — nenhum pacote é escrito")


def _arvore_suja(raiz: pathlib.Path = ROOT) -> bool:
    """Algum arquivo **rastreado**, de qualquer lugar da árvore, difere do `HEAD` (RVB4-1-07)."""
    saida = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=raiz,
                           capture_output=True, text=True, check=True).stdout
    return bool(saida.strip())


# ── As partes ───────────────────────────────────────────────────────────────────

def _texto(valor) -> str | None:
    valor = (valor or "").strip() if isinstance(valor, str) else valor
    return valor or None


def _grao(descricao: str | None) -> str | None:
    if not descricao or not descricao.startswith("**Grão:"):
        return None
    return _texto(descricao[len("**Grão:"):].split("**", 1)[0])


def _relacoes(manifest: dict) -> dict:
    saida = {}
    for no in manifest["nodes"].values():
        if no["resource_type"] not in ("model", "seed", "snapshot"):
            continue
        nome = no.get("alias") or no["name"]
        descricao = _texto(no.get("description"))
        saida[f"{no['schema']}.{nome}"] = {
            "schema": no["schema"], "name": nome, "resource_type": no["resource_type"],
            "materialization": no["config"].get("materialized"), "description": descricao,
            "meta": no.get("meta") or {}, "grain": _grao(descricao),
            "grants_select": sorted(((no["config"].get("grants") or {}).get("select")) or []),
            "columns": {c: _coluna(v) for c, v in no["columns"].items()},
        }
    for fonte in manifest["sources"].values():
        nome = fonte.get("identifier") or fonte["name"]
        descricao = _texto(fonte.get("description"))
        meta = fonte.get("meta") or {}
        saida[f"{fonte['schema']}.{nome}"] = {
            "schema": fonte["schema"], "name": nome, "resource_type": "source", "materialization": None,
            "description": descricao, "meta": meta, "grain": _grao(descricao),
            "grants_select": sorted(((meta.get("grants") or {}).get("select")) or []),
            "columns": {c: _coluna(v) for c, v in fonte["columns"].items()},
        }
    return dict(sorted(saida.items()))


def _coluna(v: dict) -> dict:
    meta = v.get("meta") or {}
    return {"description": _texto(v.get("description")), "data_type": _texto(v.get("data_type")),
            "sensitivity": meta.get("sensitivity"), "meta": meta}


def _faltas(relacoes: dict) -> list[dict]:
    saida = []
    for rid, r in relacoes.items():
        if r["description"] is None:
            saida.append({"relation": rid, "column": None})
        saida += [{"relation": rid, "column": c} for c, v in sorted(r["columns"].items()) if v["description"] is None]
    return saida


#: O cabeçalho de uma pergunta e o de um item em aberto, com qualquer espaço que o Markdown aceita.
CABECA_PERGUNTA = re.compile(r"^#{3}[ \t]+(P\d{2})[ \t]+—[ \t]+(.+?)[ \t]*$", re.M)
CABECA_ABERTO = re.compile(r"^#{3}[ \t]+(((?:D|V)\d+)[ \t]+—[ \t]+(.+?))[ \t]*$", re.M)
CELULA = re.compile(r"^\|[ \t]*\*\*(Fatos?|Medidas|Dimensões|View)\*\*[ \t]*\|[ \t]*(.+?)[ \t]*\|[ \t]*$", re.M)


def _sem_perda(o_que: str, achados: list[str], universo: list[str]) -> None:
    """Nada parcial (regra 4): o lido tem de ser o universo, sem repetição — senão, nada é escrito."""
    if len(achados) != len(set(achados)) or sorted(achados) != sorted(universo):
        raise SystemExit(f"{o_que}: lido {sorted(achados)}, esperado {sorted(universo)} — nenhum pacote é escrito")


def _medidas(celula: str, pergunta: str) -> list[dict]:
    medidas = []
    for parte in re.split(r"[ \t]*·[ \t]*", celula.strip()):
        m = re.fullmatch(r"`(\w+)`[ \t]*\(([^`]+)\)", parte.strip())
        nota = m and m.group(2).replace("**", "")
        tipo = nota and next((k for k in sorted(ADITIVIDADE, key=len, reverse=True) if nota.startswith(k)), None)
        if not tipo:
            raise SystemExit(f"{pergunta}: medida fora da forma `coluna` (aditividade, nota): {parte!r} — nenhum pacote é escrito")
        resto = nota[len(tipo):].lstrip(" ,—").strip()
        medidas.append({"column": m.group(1), "additivity": ADITIVIDADE[tipo], "note": resto or None})
    _sem_perda(f"{pergunta}: medidas", [x["column"] for x in medidas], re.findall(r"`(\w+)`[ \t]*\(", celula))
    return medidas


def _perguntas(texto: str) -> dict:
    saida = {}
    cabecas = list(CABECA_PERGUNTA.finditer(texto))
    # O universo: toda linha de título que cita um `Pnn`, com qualquer nível ou espaço.
    _sem_perda("perguntas de negócio", [c.group(1) for c in cabecas],
               re.findall(r"^#+\s*(P\d{2})\b", texto, re.M))
    _sem_perda("perguntas de negócio", [c.group(1) for c in cabecas], [f"P{i:02d}" for i in range(1, 17)])
    for cabeca, seguinte in zip(cabecas, cabecas[1:] + [None]):
        bloco = texto[cabeca.end():seguinte.start() if seguinte else len(texto)]
        lidas = CELULA.findall(bloco)
        celulas = dict(lidas)
        if len(celulas) != len(lidas) or not {"Medidas", "Dimensões", "View"} <= celulas.keys() or not (
                {"Fato", "Fatos"} & celulas.keys()):
            raise SystemExit(f"{cabeca.group(1)}: a tabela não tem uma linha de cada (Fato, Medidas, Dimensões, View): "
                             f"{[k for k, _ in lidas]} — nenhum pacote é escrito")
        fatos = celulas.get("Fato") or celulas.get("Fatos") or ""
        medidas = _medidas(celulas["Medidas"], cabeca.group(1))
        saida[cabeca.group(1)] = {
            "title": cabeca.group(2).strip(),
            "facts": [f"analytics.{f}" for f in re.findall(r"`(fact_\w+)`", fatos)],
            "measures": medidas,
            "dimensions": [f"analytics.{x}" for x in re.findall(r"`(dim_\w+)`", celulas.get("Dimensões") or "")],
            "view": "consumption." + re.search(r"`(\w+)`", celulas["View"]).group(1),
        }
    return saida


def _instante_execucao(timing: list[dict]) -> str | None:
    fim = next((t.get("completed_at") for t in timing if t.get("name") == "execute"), None)
    return fim


def _testes(manifest: dict, run: dict) -> dict:
    resultados = {r["unique_id"]: r for r in run["results"]}
    invocacao = run["metadata"]["invocation_id"]
    mesma = invocacao == manifest["metadata"]["invocation_id"]
    nos = list(manifest["nodes"].values()) + list((manifest.get("unit_tests") or {}).values())
    saida = {}
    for no in nos:
        if no["resource_type"] not in ("test", "unit_test"):
            continue
        r = resultados.get(no["unique_id"])
        unitario = no["resource_type"] == "unit_test"
        if unitario:
            alvo = no.get("model") and f"{_esquema_do_modelo(manifest, no['model'])}.{no['model']}"
            nome_teste = no["name"]
        else:
            alvo = _alvo(manifest, no)
            nome_teste = (no.get("test_metadata") or {}).get("name") or "singular"
        resultado = None
        if r is not None:
            estado = {"success": "pass"}.get(r["status"], r["status"])
            resultado = {"status": estado, "executed_at": _instante_execucao(r.get("timing") or []),
                         "invocation_id": invocacao, "same_invocation_as_manifest": mesma}
        saida[no["unique_id"]] = {
            "kind": "unit_test" if unitario else "data_test", "test": nome_teste, "relation": alvo,
            "column": no.get("column_name"), "declared_in": "dbt/" + no["original_file_path"], "result": resultado,
        }
    return dict(sorted(saida.items()))


def _esquema_do_modelo(manifest: dict, modelo: str) -> str:
    no = next(n for n in manifest["nodes"].values() if n["resource_type"] == "model" and n["name"] == modelo)
    return no["schema"]


def _alvo(manifest: dict, teste: dict) -> str | None:
    pais = teste.get("attached_node") and [teste["attached_node"]] or [
        p for p in teste["depends_on"]["nodes"] if p.startswith(("model.", "seed.", "snapshot.", "source."))]
    if len(pais) != 1:
        return None
    pai = manifest["nodes"].get(pais[0]) or manifest["sources"].get(pais[0])
    return f"{pai['schema']}.{pai.get('alias') or pai.get('identifier') or pai['name']}"


def _auditorias(resultado: dict) -> dict:
    return {f"consumption.{v}": {"status": "audited", "commit": resultado["commit"], "criteria": resultado["criteria"],
                                 "reference": linha["reference"], "findings": linha["findings"]}
            for v, linha in sorted(resultado["views"].items())}


def _resumo(modulo: pathlib.Path) -> str | None:
    try:
        doc = ast.get_docstring(ast.parse(modulo.read_text(encoding="utf-8")))
    except (OSError, SyntaxError):
        return None
    return _texto(doc.splitlines()[0]) if doc else None


def _verificacoes(junit: pathlib.Path, raiz: pathlib.Path = ROOT) -> dict:
    """O pytest do último `make test` (o do `make check`); sem relatório, `{}` — e o pacote diz que não há resultado."""
    if not junit.exists():
        return {}
    documento = ET.parse(junit).getroot()
    suite = documento if documento.tag == "testsuite" else documento.find("testsuite")
    quando = dt.datetime.fromisoformat(suite.get("timestamp")).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    execucao = f"pytest@{quando}"
    saida = {}
    for caso in suite.iter("testcase"):
        modulo, classes = _modulo_do_caso(caso.get("classname"), raiz)
        estado = ("fail" if caso.find("failure") is not None else "error" if caso.find("error") is not None
                  else "skipped" if caso.find("skipped") is not None else "pass")
        chave = "::".join([modulo, *classes, caso.get("name")])
        if chave in saida:
            raise SystemExit(f"JUnit: `{chave}` aparece duas vezes — nenhum pacote é escrito")
        saida[chave] = {
            "module": modulo, "summary": _resumo(raiz / modulo), "layer": None,
            "result": {"status": estado, "executed_at": quando, "run_id": execucao},
        }
    return dict(sorted(saida.items()))


def _modulo_do_caso(classname: str, raiz: pathlib.Path = ROOT) -> tuple[str, list[str]]:
    """`tests.sub.test_x.Classe` → (`tests/sub/test_x.py`, [`Classe`]): o módulo é o arquivo que existe (RVB4-1-04)."""
    partes = (classname or "").split(".")
    for fim in range(len(partes), 0, -1):
        modulo = "/".join(partes[:fim]) + ".py"
        if modulo.startswith("tests/") and (raiz / modulo).is_file():
            return modulo, partes[fim:]
    raise SystemExit(f"JUnit: `{classname}` não corresponde a módulo nenhum em tests/ — nenhum pacote é escrito")


def _abertos(texto: str) -> list[dict]:
    from mvp_ed1.docs_check import slug

    partes = re.split(r"^##[ \t]+1\.[ \t]+Esperando você[ \t]*$", texto, maxsplit=1, flags=re.M)
    if len(partes) != 2:
        raise SystemExit("pendências: sem a seção `## 1. Esperando você` — nenhum pacote é escrito")
    secao = partes[1]
    secao = re.split(r"^##[ \t]+1\.1\b", secao, maxsplit=1, flags=re.M)[0]
    cabecas = CABECA_ABERTO.findall(secao)
    # O universo: todo título da seção que cita um `Dnn` ou `Vn`, com qualquer nível ou espaço.
    _sem_perda("itens em aberto", [c[1] for c in cabecas], re.findall(r"^#+\s*((?:D|V)\d+)\b", secao, re.M))
    saida = []
    for titulo, ident, nome in cabecas:
        adiada = "adiada" in nome or ident.startswith("V")
        saida.append({"id": ident, "title": nome.strip(), "state": "deferred" if adiada else "pending",
                      "anchor": f"docs/pendencias.md#{slug(titulo)}", "objects": None})
    return saida


# ── O pacote ────────────────────────────────────────────────────────────────────

def montar(manifest: dict, derivacao, run: dict, junit: pathlib.Path = JUNIT) -> dict:
    linhagem = lineage.build(manifest, derivacao)
    if linhagem.problems:
        raise SystemExit(f"linhagem incompleta ({len(linhagem.problems)} problema(s)): pacote não escrito")
    caminhos = insumos()
    relacoes = _relacoes(manifest)
    perfil = yaml.safe_load((DBT / "profiles.yml").read_text(encoding="utf-8"))
    alvo = next(iter(perfil.values()))["target"]
    return {
        "format": FORMATO,
        "provenance": {
            "inputs_sha256": digest(caminhos), "inputs": caminhos,
            "tree_dirty_at_generation": _arvore_suja(),
            "environment": {"dbt_target": alvo},
            "dbt": {"dbt_version": manifest["metadata"]["dbt_version"], "adapter_type": manifest["metadata"]["adapter_type"],
                    "manifest_generated_at": manifest["metadata"]["generated_at"],
                    "manifest_invocation_id": manifest["metadata"]["invocation_id"],
                    "run_results_generated_at": run["metadata"]["generated_at"],
                    "run_results_invocation_id": run["metadata"]["invocation_id"]},
            "warehouse": {"status": "not_verified", "built_by_invocation_id": None},
            "link_base": "docs/",
        },
        "relations": relacoes,
        "lineage": lineage.to_json(linhagem, manifest),
        "crossings": [dict(zip(("origin", "destination", "mechanism", "frequency", "note"), c)) for c in lineage.crossings()],
        "questions": _perguntas(PERGUNTAS.read_text(encoding="utf-8")),
        "description_gaps": _faltas(relacoes),
        "tests": _testes(manifest, run),
        "view_audits": _auditorias(yaml.safe_load(RESULTADO.read_text(encoding="utf-8"))),
        "environments": AMBIENTES,
        "checks": _verificacoes(junit),
        "open_items": _abertos(PENDENCIAS.read_text(encoding="utf-8")),
    }


def serializar(pacote: dict) -> str:
    return json.dumps(pacote, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


#: Caminho absoluto de máquina (regra 7): o que o repositório não tem e não pode publicar.
CAMINHO_DE_FORA = re.compile(r"(?<![\w.~/-])(?:/(?:home|opt|usr|tmp|var|etc|root|mnt|srv|Users|private)/|[A-Za-z]:\\)")


def _instante(valor: object) -> bool:
    """O calendário que a expressão do esquema não alcança (regra 6): 31/02 não passa (RVB4-1-06)."""
    if not isinstance(valor, str):
        return True
    try:
        return dt.datetime.fromisoformat(valor).tzinfo is not None
    except ValueError:
        return False


def _cadeias(no, onde: str = ""):
    """Toda cadeia do pacote, **chaves inclusive**, com onde está."""
    if isinstance(no, dict):
        for k, v in no.items():
            yield f"{onde}{{chave}}", k
            yield from _cadeias(v, f"{onde}.{k}")
    elif isinstance(no, list):
        for i, v in enumerate(no):
            yield from _cadeias(v, f"{onde}[{i}]")
    elif isinstance(no, str):
        yield onde, no


def validar(pacote: dict) -> list[str]:
    import jsonschema

    esquema = json.loads(ESQUEMA.read_text(encoding="utf-8"))
    esquema["$defs"]["instante"]["format"] = "instante-no-calendario"
    formatos = copy.deepcopy(jsonschema.Draft202012Validator.FORMAT_CHECKER)
    formatos.checks("instante-no-calendario")(_instante)
    erros = [e.message for e in jsonschema.Draft202012Validator(esquema, format_checker=formatos).iter_errors(pacote)]
    erros += [f"caminho fora do repositório em {onde}: …{texto[max(m.start() - 20, 0):m.end() + 40]!r}"
              for onde, texto in _cadeias(pacote) if (m := CAMINHO_DE_FORA.search(texto))]
    return sorted(erros)


#: O que muda a cada execução sem mudar o que o pacote afirma: fora da comparação do `--check`.
EXECUCAO = {"executed_at", "invocation_id", "same_invocation_as_manifest", "run_id"}


def normalizado(pacote: dict) -> dict:
    """O pacote sem os instantes e as execuções: o que tem de ser igual entre o versionado e o de agora."""
    p = copy.deepcopy(pacote)
    p["provenance"].pop("tree_dirty_at_generation", None)
    p["provenance"]["dbt"] = {k: v for k, v in p["provenance"]["dbt"].items() if not k.startswith(("manifest_", "run_results_"))}
    for secao in ("tests", "checks"):
        for item in p[secao].values():
            if item.get("result"):
                item["result"] = {k: v for k, v in item["result"].items() if k not in EXECUCAO}
    return p


def diferencas(versionado: dict, atual: dict, limite: int = 8) -> list[str]:
    """Onde os dois pacotes normalizados divergem, seção a seção, com alguns exemplos de chave."""
    a, b = normalizado(versionado), normalizado(atual)
    saida = []
    for secao in sorted(a.keys() | b.keys()):
        x, y = a.get(secao), b.get(secao)
        if x == y:
            continue
        if isinstance(x, dict) and isinstance(y, dict):
            chaves = sorted(k for k in x.keys() | y.keys() if x.get(k) != y.get(k))
            saida.append(f"{secao}: {len(chaves)} diferente(s), p.ex. {chaves[:limite]}")
        else:
            saida.append(f"{secao}: diferente")
    return saida


def _montar_conferido() -> dict | int:
    for artefato in (MANIFEST, RUN_RESULTS):
        if not artefato.exists():
            print(f"sem {artefato.relative_to(ROOT)}; rode `make dbt-build` antes — nenhum pacote é escrito", file=sys.stderr)
            return 2
    manifest, derivacao = sensitivity.load()
    conferir_carimbo(manifest, digest_do_dbt())
    run = json.loads(RUN_RESULTS.read_text(encoding="utf-8"))
    pacote = montar(manifest, derivacao, run)
    erros = validar(pacote)
    if erros:
        print(f"pacote fora do esquema ou das regras ({len(erros)}): nada é escrito; p.ex. {erros[:3]}", file=sys.stderr)
        return 1
    return pacote


def conferir() -> int:
    """`--check`: o versionado é o que os artefatos de agora dão, salvo instantes e execuções (RVB4-1-01)."""
    pacote = _montar_conferido()
    if isinstance(pacote, int):
        return pacote
    if not PACOTE.exists():
        print("docs/pacote_de_metadados.json não existe; rode `make catalog`", file=sys.stderr)
        return 1
    if diferenca := diferencas(json.loads(PACOTE.read_text(encoding="utf-8")), pacote):
        print("pacote de metadados atrasado em relação aos artefatos desta execução; rode `make catalog` e "
              "versione o resultado:\n  " + "\n  ".join(diferenca), file=sys.stderr)
        return 1
    print(f"pacote de metadados em dia com os artefatos ({len(pacote['tests'])} testes, {len(pacote['checks'])} do pytest)")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--digest-do-dbt"]:
        print(digest_do_dbt())
        return 0
    if argv[:1] == ["--carimbar"] and len(argv) == 3:
        carimbar(argv[1], argv[2])
        return 0
    if argv[:1] == ["--check"]:
        return conferir()
    if argv:
        print(f"uso: python -m mvp_ed1.models.pacote [--check | --digest-do-dbt | --carimbar DIGEST INICIO]; recebido {argv}",
              file=sys.stderr)
        return 2
    pacote = _montar_conferido()
    if isinstance(pacote, int):
        return pacote
    texto = serializar(pacote)
    if PACOTE.exists() and PACOTE.read_text(encoding="utf-8") == texto:
        print(f"pacote de metadados já em dia ({len(pacote['relations'])} relações)")
        return 0
    PACOTE.write_text(texto, encoding="utf-8")
    print(f"pacote de metadados escrito: {len(pacote['relations'])} relações, {len(pacote['tests'])} testes, "
          f"{len(pacote['checks'])} do pytest, {len(pacote['open_items'])} itens em aberto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
