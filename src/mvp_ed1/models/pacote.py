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
"""

from __future__ import annotations

import ast
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
)

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


def digest(caminhos: list[str], raiz: pathlib.Path = ROOT, conteudo=None) -> str:
    """SHA-256 de `caminho\\0sha256(conteúdo)\\n` em ordem. `conteudo` troca a leitura (contraprovas)."""
    h = hashlib.sha256()
    for c in caminhos:
        dados = conteudo(c) if conteudo else (raiz / c).read_bytes()
        h.update(c.encode() + b"\0" + hashlib.sha256(dados).hexdigest().encode() + b"\n")
    return h.hexdigest()


def _arvore_suja(caminhos: list[str]) -> bool:
    saida = subprocess.run(["git", "status", "--porcelain", "--", *caminhos], cwd=ROOT, capture_output=True, text=True, check=True).stdout
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


def _perguntas(texto: str) -> dict:
    saida = {}
    for bloco in re.split(r"\n(?=### P\d{2} — )", texto):
        cabeca = re.match(r"### (P\d{2}) — (.+)", bloco)
        if not cabeca:
            continue
        celulas = dict(re.findall(r"^\| \*\*(Fatos?|Medidas|Dimensões|View)\*\* \| (.+) \|$", bloco, re.M))
        fatos = celulas.get("Fato") or celulas.get("Fatos") or ""
        medidas = []
        for parte in (celulas.get("Medidas") or "").split(" · "):
            m = re.match(r"`(\w+)`\s*\((.+)\)\s*$", parte.strip())
            if not m:
                continue
            nota = m.group(2).replace("**", "")
            tipo = next(k for k in sorted(ADITIVIDADE, key=len, reverse=True) if nota.startswith(k))
            resto = nota[len(tipo):].lstrip(" ,—").strip()
            medidas.append({"column": m.group(1), "additivity": ADITIVIDADE[tipo], "note": resto or None})
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


def _verificacoes(junit: pathlib.Path) -> dict:
    """O pytest do último `make check`; sem relatório, `{}` — e o pacote diz que não há resultado."""
    if not junit.exists():
        return {}
    raiz = ET.parse(junit).getroot()
    suite = raiz if raiz.tag == "testsuite" else raiz.find("testsuite")
    quando = dt.datetime.fromisoformat(suite.get("timestamp")).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    execucao = f"pytest@{quando}"
    saida = {}
    for caso in suite.iter("testcase"):
        modulo = "tests/" + caso.get("classname").removeprefix("tests.").split(".")[0] + ".py"
        estado = ("fail" if caso.find("failure") is not None else "error" if caso.find("error") is not None
                  else "skipped" if caso.find("skipped") is not None else "pass")
        saida[f"{modulo}::{caso.get('name')}"] = {
            "module": modulo, "summary": _resumo(ROOT / modulo), "layer": None,
            "result": {"status": estado, "executed_at": quando, "run_id": execucao},
        }
    return dict(sorted(saida.items()))


def _abertos(texto: str) -> list[dict]:
    from mvp_ed1.docs_check import slug

    secao = texto.split("\n## 1. Esperando você", 1)[1].split("\n## 1.1", 1)[0]
    saida = []
    for titulo in re.findall(r"^### ((?:D|V)\d+ — .+)$", secao, re.M):
        ident, nome = titulo.split(" — ", 1)
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
            "tree_dirty_at_generation": _arvore_suja(caminhos),
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


def validar(pacote: dict) -> list[str]:
    import jsonschema

    esquema = json.loads(ESQUEMA.read_text(encoding="utf-8"))
    return sorted(e.message for e in jsonschema.Draft202012Validator(esquema).iter_errors(pacote))


def main(argv: list[str] | None = None) -> int:
    for artefato in (MANIFEST, RUN_RESULTS):
        if not artefato.exists():
            print(f"sem {artefato.relative_to(ROOT)}; rode `make dbt-build` antes — nenhum pacote é escrito", file=sys.stderr)
            return 2
    manifest, derivacao = sensitivity.load()
    run = json.loads(RUN_RESULTS.read_text(encoding="utf-8"))
    pacote = montar(manifest, derivacao, run)
    erros = validar(pacote)
    if erros:
        print(f"pacote fora do esquema ({len(erros)}): nada é escrito; p.ex. {erros[:3]}", file=sys.stderr)
        return 1
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
