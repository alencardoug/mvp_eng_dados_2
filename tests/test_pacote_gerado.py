"""O pacote de metadados versionado está em dia com os insumos (D91, guarda do RVG-1-04).

Roda no `check-offline`, sem banco e sem `dbt/target`: o pacote se confere pelo
`inputs_sha256`, recalculado dos arquivos rastreados que o alimentam. Insumo mudado
sem `make catalog` falha aqui; *commit* que não mexe nos insumos não invalida nada.

As contraprovas que o RVG-1-04 pede:
* **clone sem artefatos** — a guarda roda num clone do repositório, sem `dbt/target`;
* **regeneração repetida** — com os mesmos artefatos, o mesmo texto (integração);
* **commit posterior sem mudança dos insumos** — o digest não muda.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import jsonschema
import pytest

from mvp_ed1.models import pacote

RAIZ = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gerado() -> dict:
    if not pacote.PACOTE.exists():
        pytest.fail("docs/pacote_de_metadados.json não existe; rode `make catalog`")
    return json.loads(pacote.PACOTE.read_text(encoding="utf-8"))


def test_o_pacote_cumpre_o_esquema(gerado) -> None:
    esquema = json.loads(pacote.ESQUEMA.read_text(encoding="utf-8"))
    erros = sorted(e.message for e in jsonschema.Draft202012Validator(esquema).iter_errors(gerado))
    assert erros == []


def test_o_pacote_esta_em_dia_com_os_insumos(gerado) -> None:
    caminhos = pacote.insumos()
    assert gerado["provenance"]["inputs"] == caminhos, "insumo novo ou removido: rode `make catalog`"
    assert gerado["provenance"]["inputs_sha256"] == pacote.digest(caminhos), "insumo mudou: rode `make catalog`"


def test_o_pacote_esta_na_forma_deterministica(gerado) -> None:
    assert pacote.PACOTE.read_text(encoding="utf-8") == pacote.serializar(gerado)


def test_um_insumo_alterado_muda_o_digest() -> None:
    """Contraprova: a guarda acusa a mudança de qualquer insumo."""
    caminhos = pacote.insumos()
    original = pacote.digest(caminhos)
    alvo = "docs/glossario_de_negocio/receita_liquida.md"
    assert alvo in caminhos
    # O controle sem mutação primeiro: a leitura do callback é a do digest, e só o alvo muda (RVB4-2-06).
    assert pacote.digest(caminhos, conteudo=lambda c: pacote._conteudo(RAIZ, c)) == original
    alterado = pacote.digest(caminhos, conteudo=lambda c: pacote._conteudo(RAIZ, c) + (b"x" if c == alvo else b""))
    assert alterado != original


def test_um_commit_sem_mudanca_nos_insumos_nao_muda_o_digest() -> None:
    """O digest depende só do conteúdo dos insumos, não do commit nem da hora."""
    caminhos = pacote.insumos()
    assert pacote.digest(caminhos) == pacote.digest(list(caminhos))


def test_a_guarda_roda_num_clone_sem_artefatos(tmp_path) -> None:
    """Contraprova do clone limpo: no HEAD clonado, sem `dbt/target`, o digest é calculável e é o do pacote dele."""
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(RAIZ), str(clone)], check=True)
    assert not (clone / "dbt" / "target").exists()
    versionado = clone / "docs" / "pacote_de_metadados.json"
    if not versionado.exists():
        pytest.skip("o HEAD ainda não tem o pacote (o primeiro commit dele)")
    # A guarda **do clone**, com o código e os arquivos dele: com o código do diretório de trabalho, uma
    # mudança ainda não versionada em `INSUMOS` faria o HEAD parecer atrasado — e o pacote, que publica
    # o resultado deste teste, carregaria essa falha (Bloco 4, rodada 1).
    programa = ("import json, sys; sys.path.insert(0, 'src'); from mvp_ed1.models import pacote; "
                "c = pacote.insumos(); print(json.dumps([pacote.__file__, c, pacote.digest(c)]))")
    saida = subprocess.run([sys.executable, "-c", programa], cwd=clone, capture_output=True, text=True, check=True)
    arquivo, caminhos, calculado = json.loads(saida.stdout)
    assert pathlib.Path(arquivo).resolve().is_relative_to(clone.resolve()), arquivo
    dado = json.loads(versionado.read_text(encoding="utf-8"))
    assert dado["provenance"]["inputs"] == caminhos
    assert dado["provenance"]["inputs_sha256"] == calculado


@pytest.mark.integracao
def test_a_regeneracao_repetida_da_o_mesmo_texto() -> None:
    """Com os mesmos artefatos, duas montagens dão os mesmos bytes."""
    if not (pacote.MANIFEST.exists() and pacote.RUN_RESULTS.exists()):
        pytest.skip("sem os artefatos do dbt")
    from mvp_ed1.models import sensitivity

    manifest, derivacao = sensitivity.load()
    run = json.loads(pacote.RUN_RESULTS.read_text(encoding="utf-8"))
    assert pacote.serializar(pacote.montar(manifest, derivacao, run)) == pacote.serializar(pacote.montar(manifest, derivacao, run))


# ── A revisão do Bloco 4, rodada 1 (RVB4-1-01 a 07) ─────────────────────────────

def test_o_resumo_de_um_modulo_de_teste_entra_no_digest_e_o_resto_do_codigo_nao(tmp_path) -> None:
    """RVB4-1-01: o `summary` de `checks` é lido do módulo; mudar a docstring muda o digest."""
    caminhos = pacote.insumos()
    assert "tests/test_acesso.py" in caminhos and "dbt/profiles.yml" in caminhos
    assert "src/mvp_ed1/docs_check.py" in caminhos
    original = pacote.digest(caminhos)
    docstring = pacote.digest(caminhos, conteudo=lambda c: b"outro resumo" if c == "tests/test_acesso.py"
                              else pacote._conteudo(RAIZ, c))
    assert docstring != original
    modulo = tmp_path / "tests" / "test_x.py"
    modulo.parent.mkdir()
    modulo.write_text('"""O resumo.\n\nMais texto."""\nx = 1\n', encoding="utf-8")
    antes = pacote._conteudo(tmp_path, "tests/test_x.py")
    modulo.write_text('"""O resumo.\n\nOutro texto."""\nx = 2\n', encoding="utf-8")
    assert pacote._conteudo(tmp_path, "tests/test_x.py") == antes == b"O resumo."   # só a 1ª linha conta
    modulo.write_text('"""Outro resumo."""\n', encoding="utf-8")
    assert pacote._conteudo(tmp_path, "tests/test_x.py") != antes


def _manifest(invocacao: str, gerado: str = "2026-11-14T12:00:00.5Z") -> dict:
    return {"metadata": {"invocation_id": invocacao, "generated_at": gerado}}


def test_o_carimbo_recusa_manifest_de_outra_execucao_ou_de_outros_insumos(tmp_path) -> None:
    """RVB4-1-02: a contraprova do revisor — declaração mudou, *manifest* ficou; o pacote não sai."""
    manifest, carimbo = tmp_path / "manifest.json", tmp_path / "carimbo.json"
    manifest.write_text(json.dumps(_manifest("inv-1")), encoding="utf-8")
    with pytest.raises(SystemExit, match="sem carimbo|sem carimbo.json|não veio"):
        pacote.conferir_carimbo(_manifest("inv-1"), "d1", carimbo)
    assert pacote.carimbar("d1", "-", manifest, carimbo)                             # não havia manifest
    pacote.conferir_carimbo(_manifest("inv-1"), "d1", carimbo)                       # o par certo passa
    with pytest.raises(SystemExit, match="outra execução"):
        pacote.conferir_carimbo(_manifest("inv-2"), "d1", carimbo)                   # `dbt parse` à mão
    with pytest.raises(SystemExit, match="mudaram depois"):
        pacote.conferir_carimbo(_manifest("inv-1"), "d2", carimbo)                   # descrição editada


def test_o_carimbo_nao_vai_para_o_manifest_anterior_ao_build(tmp_path) -> None:
    """O dbt falhou antes de escrever o *manifest*: o que está lá é o de antes, e o carimbo sai.

    RVB4-2-05: decide a invocação, não o relógio — o *manifest* do mesmo segundo (ou do mesmo
    microssegundo) que o início do comando não é carimbado se é o que havia antes.
    """
    manifest, carimbo = tmp_path / "manifest.json", tmp_path / "carimbo.json"
    manifest.write_text(json.dumps(_manifest("velho", "2026-11-14T12:00:00.100000Z")), encoding="utf-8")
    assert pacote.invocacao_do_manifest(manifest) == "velho"
    carimbo.write_text("{}", encoding="utf-8")
    assert not pacote.carimbar("d1", "velho", manifest, carimbo)
    assert not carimbo.exists()
    manifest.write_text(json.dumps(_manifest("novo", "2026-11-14T12:00:00.100000Z")), encoding="utf-8")
    assert pacote.carimbar("d1", "velho", manifest, carimbo)                       # reescrito: carimba
    assert pacote.invocacao_do_manifest(tmp_path / "nao_existe.json") == "-"


def test_o_digest_do_dbt_cobre_todo_arquivo_que_o_dbt_le() -> None:
    """RVB4-2-02: o universo sai do `dbt_project.yml`, e não da lista do gerador — oráculo independente."""
    import yaml

    projeto = yaml.safe_load((RAIZ / "dbt" / "dbt_project.yml").read_text(encoding="utf-8"))
    pastas = [str((RAIZ / "dbt" / d).resolve().relative_to(RAIZ)) for chave, valores in projeto.items()
              if chave.endswith("-paths") and chave not in ("clean-targets",) for d in valores]
    rastreados = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.split()
    lidos = {c for c in rastreados if any(c.startswith(p + "/") for p in pastas)} | {"dbt/dbt_project.yml", "dbt/profiles.yml"}
    caminhos = [c for c in pacote.insumos() if c.startswith(pacote.INSUMOS_DO_DBT)]
    assert "dbt/models/_convencoes.md" in lidos
    assert sorted(lidos - set(caminhos)) == []
    assert not any(c.startswith(("tests/", "src/", "docs/pendencias")) for c in caminhos)
    assert pacote.digest_do_dbt() == pacote.digest(caminhos)


def test_um_bloco_de_convencao_alterado_muda_o_digest_do_dbt() -> None:
    """A contraprova do revisor: `_convencoes.md` editado tem de invalidar o carimbo."""
    caminhos = [c for c in pacote.insumos() if c.startswith(pacote.INSUMOS_DO_DBT)]
    alvo = "dbt/models/_convencoes.md"
    assert pacote.digest(caminhos, conteudo=lambda c: pacote._conteudo(RAIZ, c)) == pacote.digest_do_dbt()
    assert pacote.digest(caminhos, conteudo=lambda c: pacote._conteudo(RAIZ, c) + (b"x" if c == alvo else b"")) != \
        pacote.digest_do_dbt()


PERGUNTA = """### P01 — Receita
| Campo | Valor |
|---|---|
| **Fato** | `fact_sales_order_item` |
| **Medidas** | `net_revenue_amount` (aditiva) · `order_count` (não aditiva, conta pedidos) |
| **Dimensões** | `dim_date`, `dim_channel` |
| **View** | `revenue_by_month` |
"""


def _dezesseis(bloco: str) -> str:
    return "\n".join(bloco.replace("P01", f"P{i:02d}") for i in range(1, 17))


@pytest.mark.parametrize("variante", [
    pytest.param(lambda t: t, id="como-esta"),
    pytest.param(lambda t: t.replace("### P01 —", "###  P01  —", 1), id="espaco-no-titulo"),
    pytest.param(lambda t: t.replace(" · ", "·", 1), id="separador-sem-espaco"),
    pytest.param(lambda t: t.replace("| **View** |", "|  **View**  |", 1), id="espaco-na-celula"),
])
def test_espaco_que_o_markdown_aceita_nao_perde_pergunta_nem_medida(variante) -> None:
    """RVB4-1-03: as três contraprovas do revisor, e o espaço na célula."""
    perguntas = pacote._perguntas(variante(_dezesseis(PERGUNTA)))
    assert sorted(perguntas) == [f"P{i:02d}" for i in range(1, 17)]
    assert [m["column"] for m in perguntas["P01"]["measures"]] == ["net_revenue_amount", "order_count"]
    assert perguntas["P01"]["measures"][1] == {"column": "order_count", "additivity": "non_additive", "note": "conta pedidos"}


@pytest.mark.parametrize(("variante", "motivo"), [
    pytest.param(lambda t: t.replace("### P01 —", "### P01:", 1), "perguntas", id="titulo-nao-reconhecido"),
    pytest.param(lambda t: t.replace("(aditiva)", "(aditivo)", 1), "medida fora da forma", id="aditividade-desconhecida"),
    pytest.param(lambda t: t.replace("| **View** | `revenue_by_month` |\n", "", 1), "tabela", id="sem-view"),
    pytest.param(lambda t: t.replace("### P16", "### P17"), "perguntas", id="fora-de-P01-a-P16"),
])
def test_o_que_o_leitor_nao_reconhece_recusa_o_pacote(variante, motivo) -> None:
    with pytest.raises(SystemExit, match=motivo):
        pacote._perguntas(variante(_dezesseis(PERGUNTA)))


PENDENCIAS = """| Campo | Informação |
|---|---|
| Verificações e trabalho adiados | 1 (V1, as verificações) |
| Decisões pendentes | 2 (D63, o medidor; D43, adiada). A D65 foi fechada |

## 1. Esperando você

### D63 — o medidor

### D43 — a guarda (adiada em 16/09/2026)

### V1 — verificações

## 1.1 Decididas
"""
REGISTRO = "## 3. Decisões pendentes\n\n| # | Decisão |\n|---|---|\n| D43 | a guarda |\n\n## 4. Outra\n"


def _lidos(texto: str) -> list[str]:
    return [i["id"] for i in pacote._abertos(texto, REGISTRO)]


def test_os_itens_em_aberto_sao_os_que_o_cabecalho_nomeia() -> None:
    assert _lidos(PENDENCIAS) == ["D63", "D43", "V1"]
    assert [i["state"] for i in pacote._abertos(PENDENCIAS, REGISTRO)] == ["pending", "deferred", "deferred"]
    assert _lidos(PENDENCIAS.replace("### D63 —", "###  D63  —")) == ["D63", "D43", "V1"]
    assert _lidos(PENDENCIAS.replace("### D63 —", "   ### D63 —")) == ["D63", "D43", "V1"]
    # Exemplo, código e citação que não começam linha por um identificador não viram item, e não recusam.
    for inocente in ("> ## 2. Exemplo\n\n", "```exemplo```\n\n", "> ```text\n> exemplo\n\n", "- ## 1.1 Exemplo\n\n",
                     "Parágrafo que cita a D65 no meio.\n\n", "D63 começa a linha, mas está declarada.\n\n"):
        assert _lidos(PENDENCIAS.replace("### V1 —", inocente + "### V1 —", 1)) == ["D63", "D43", "V1"], inocente


@pytest.mark.parametrize("novo", [
    # RVB4-6-01: item novo fora da forma canônica, com o cabeçalho sem ele — a regra de autoria o pega.
    pytest.param("#### D93 — nova decisão operacional\n\n", id="nivel-4"),
    pytest.param("D93 — nova decisão\n---\n\n", id="setext"),
    pytest.param("#### V5 — nova verificação adiada\n\n", id="verificacao"),
    pytest.param("### [D93](#d93) — nova\n\n", id="link"),
    # A regra é de autoria, e de propósito: parágrafo ou código que começa por um ID não declarado recusa.
    pytest.param("D93 é um parágrafo\n\n", id="paragrafo"), pytest.param("    **D93** é código\n\n", id="codigo"),
])
def test_linha_que_comeca_por_id_nao_declarado_recusa(novo) -> None:
    with pytest.raises(SystemExit, match="D93|V5"):
        pacote._abertos(PENDENCIAS.replace("### V1 —", novo + "### V1 —", 1), REGISTRO)


@pytest.mark.parametrize(("linha", "motivo"), [
    # RVB4-6-02: nenhuma linha da tabela do Registro some por estar em código ou link.
    pytest.param("| `D93` | nova |", "Registro tem", id="codigo"),
    pytest.param("| [D93](#3-decisões-pendentes) | nova |", "Registro tem", id="link"),
    pytest.param("| **D93** | nova |", "Registro tem", id="negrito"),
    pytest.param("| — | sem identificador |", "não tem um `Dnn`", id="sem-id"),
    pytest.param("| D93 e D94 | duas |", "não tem um `Dnn`", id="dois-ids"),
])
def test_toda_linha_da_tabela_do_registro_conta(linha, motivo) -> None:
    with pytest.raises(SystemExit, match=motivo):
        pacote._abertos(PENDENCIAS, REGISTRO.replace("| D43 |", linha + "\n| D43 |"))


@pytest.mark.parametrize("estranho", [
    # As formas das rodadas 2 a 5 (RVB4-2-03, 3-02, 4-01, 5-03, 5-04): o item que o cabeçalho nomeia e o leitor
    # não acha na forma canônica recusa a geração — nenhuma delas o perde em silêncio.
    pytest.param("### **D63** —", id="negrito"), pytest.param("#### D63 —", id="nivel-4"),
    pytest.param("D63 — sublinhado\n---\n", id="setext"), pytest.param("**D63** — sublinhado\n---\n", id="setext-negrito"),
    pytest.param("D63 — em duas\nlinhas\n---\n", id="setext-duas-linhas"),
    pytest.param("Nota.\n<!-- c -->\nD63 — sublinhado\n---\n", id="comentario-e-setext"),
    pytest.param("### [D63](#d63) —", id="link"), pytest.param("> ### D63 —", id="citado"),
])
def test_o_item_fora_da_forma_canonica_recusa(estranho) -> None:
    with pytest.raises(SystemExit, match="itens em aberto"):
        pacote._abertos(PENDENCIAS.replace("### D63 —", estranho, 1), REGISTRO)


def test_a_declaracao_tem_de_se_sustentar() -> None:
    """Cópia do item, cabeçalho que conta e não nomeia, Registro com pendente fora do cabeçalho: recusa."""
    with pytest.raises(SystemExit, match="itens em aberto"):                                   # cópia num exemplo
        pacote._abertos(PENDENCIAS.replace("### V1 —", "```\n### D63 — exemplo\n```\n\n### V1 —", 1), REGISTRO)
    with pytest.raises(SystemExit, match="conta 3"):
        pacote._abertos(PENDENCIAS.replace("| 2 (D63", "| 3 (D63", 1), REGISTRO)
    with pytest.raises(SystemExit, match="Registro tem"):
        pacote._abertos(PENDENCIAS, REGISTRO.replace("| D43 |", "| D43 |\n| D99 | outra |"))
    with pytest.raises(SystemExit, match="Esperando você"):
        pacote._abertos(PENDENCIAS.replace("## 1. Esperando você", "## 1. Outra coisa"), REGISTRO)
    with pytest.raises(SystemExit, match="não tem a linha"):
        pacote._abertos(PENDENCIAS.replace("| Decisões pendentes |", "| Decisões |"), REGISTRO)


@pytest.mark.parametrize("variante", [
    pytest.param(lambda t: t.replace("### P05 —", "### [P05](#p05) —", 1), id="link"),
    pytest.param(lambda t: t.replace("### P05 —", "> ### P05 —", 1), id="citada"),
    pytest.param(lambda t: t.replace("### P05 —", "P05 —", 1).replace("| Campo | Valor |", "---\n| Campo | Valor |", 5), id="setext"),
    pytest.param(lambda t: t + "\n```\n### P05 — cópia\n```\n", id="copia-em-cerca"),
])
def test_a_pergunta_fora_da_forma_ou_copiada_recusa(variante) -> None:
    """As 16 perguntas são as do contrato: escondida falta, copiada se repete."""
    with pytest.raises(SystemExit, match="perguntas"):
        pacote._perguntas(variante(_dezesseis(PERGUNTA)))


def _junit(tmp_path, *casos: str) -> pathlib.Path:
    arquivo = tmp_path / "junit.xml"
    arquivo.write_text('<testsuites><testsuite timestamp="2026-11-14T11:00:00-03:00">'
                       + "".join(casos) + "</testsuite></testsuites>", encoding="utf-8")
    return arquivo


def test_o_junit_resolve_o_modulo_pelo_arquivo_e_guarda_a_classe(tmp_path) -> None:
    """RVB4-1-04: subdiretório, classe e homônimos não colidem."""
    for modulo in ("tests/test_a.py", "tests/sub/test_a.py", "tests/sub/test_b.py"):
        (tmp_path / modulo).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / modulo).write_text(f'"""Resumo de {modulo}."""\n', encoding="utf-8")
    junit = _junit(tmp_path, '<testcase classname="tests.sub.test_a" name="test_x"/>',
                   '<testcase classname="tests.sub.test_b" name="test_x"><failure/></testcase>',
                   '<testcase classname="tests.test_a.Classe" name="test_x"/>',
                   '<testcase classname="tests.test_a" name="test_x"/>')
    checks = pacote._verificacoes(junit, tmp_path)
    assert sorted(checks) == ["tests/sub/test_a.py::test_x", "tests/sub/test_b.py::test_x",
                              "tests/test_a.py::Classe::test_x", "tests/test_a.py::test_x"]
    assert checks["tests/sub/test_b.py::test_x"]["result"]["status"] == "fail"
    assert checks["tests/sub/test_a.py::test_x"]["summary"] == "Resumo de tests/sub/test_a.py."


def test_o_junit_recusa_modulo_inexistente_e_caso_repetido(tmp_path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="não corresponde"):
        pacote._verificacoes(_junit(tmp_path, '<testcase classname="tests.test_sumiu" name="t"/>'), tmp_path)
    with pytest.raises(SystemExit, match="duas vezes"):
        pacote._verificacoes(_junit(tmp_path, '<testcase classname="tests.test_a" name="t"/>',
                                    '<testcase classname="tests.test_a" name="t"/>'), tmp_path)


def _minimo(gerado: dict) -> dict:
    """O pacote versionado como base das contraprovas de `validar`."""
    return json.loads(json.dumps(gerado))


def test_caminho_de_maquina_em_chave_ou_valor_e_recusado(gerado) -> None:
    """RVB4-1-05: a regra 7 sobre o pacote inteiro, chaves inclusive."""
    base = _minimo(gerado)
    base["checks"] = {}
    assert not [e for e in pacote.validar(base) if "caminho fora" in e]
    chave = dict(base, checks={"tests/test_x.py::test_y[/opt/python3.11/lib/x.py:50]": {
        "module": "tests/test_x.py", "summary": None, "layer": None, "result": None}})
    assert any("caminho fora" in e for e in pacote.validar(chave))
    valor = _minimo(base)
    valor["environments"][0]["note"] = "ver /home/alguem/projeto"
    assert any("caminho fora" in e for e in pacote.validar(valor))
    assert not pacote.CAMINHO_DE_FORA.search("docs/arquitetura.md#5 e https://exemplo.org/home/x")


def test_o_calendario_de_todo_instante_e_conferido(gerado) -> None:
    """RVB4-1-06: 31/02 passa na expressão do esquema e não passa no gerador."""
    base = _minimo(gerado)
    base["provenance"]["dbt"]["manifest_generated_at"] = "2026-02-31T00:00:00Z"
    assert any("instante-no-calendario" in e for e in pacote.validar(base))
    assert pacote._instante("2026-11-14T14:05:25.720202Z") and not pacote._instante("2026-11-14T14:05:25")


def test_a_arvore_suja_olha_todo_arquivo_rastreado(tmp_path) -> None:
    """RVB4-1-07: mudança só no README, fora dos insumos, deixa a árvore suja."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"], check=True)
    assert not pacote._arvore_suja(tmp_path)
    (tmp_path / "solto.txt").write_text("não rastreado\n", encoding="utf-8")
    assert not pacote._arvore_suja(tmp_path)
    (tmp_path / "README.md").write_text("b\n", encoding="utf-8")
    assert pacote._arvore_suja(tmp_path)


def test_a_conferencia_ignora_a_execucao_e_acusa_o_resultado(gerado) -> None:
    """RVB4-1-01: outro instante e outra execução não atrasam o pacote; outro resultado, sim."""
    base = _minimo(gerado)
    if not base["tests"]:
        pytest.skip("pacote sem testes do dbt")
    outra = _minimo(base)
    outra["provenance"]["tree_dirty_at_generation"] = not base["provenance"]["tree_dirty_at_generation"]
    outra["provenance"]["dbt"]["manifest_invocation_id"] = "outra"
    for item in outra["tests"].values():
        if item["result"]:
            item["result"]["executed_at"], item["result"]["invocation_id"] = "2030-01-01T00:00:00Z", "outra"
    assert pacote.diferencas(base, outra) == []
    teste = next(k for k, v in outra["tests"].items() if v["result"])
    outra["tests"][teste]["result"]["status"] = "fail"
    assert pacote.diferencas(base, outra) == [f"tests: 1 diferente(s), p.ex. {[teste]}"]
    # Um teste do pytest a mais (ou a menos) atrasa o pacote — sem supor `checks` cheio: no primeiro
    # `make catalog` da sequência de publicação ele é vazio, por desenho.
    novo = _minimo(base)
    novo["checks"]["tests/test_x.py::test_novo"] = {"module": "tests/test_x.py", "summary": None, "layer": None,
                                                    "result": None}
    assert pacote.diferencas(base, novo) == ["checks: 1 diferente(s), p.ex. ['tests/test_x.py::test_novo']"]


def test_junit_parcial_ou_de_outra_colecao_nao_e_completo() -> None:
    """RVB4-2-04: o oráculo é a coleta; o gerador publica `checks` vazio, sem resultado, em vez do parcial."""
    casos = ["tests/test_a.py::test_x", "tests/test_a.py::test_y"]
    assert pacote.completo(dict.fromkeys(casos, {}), casos) is None
    assert "1 caso(s) da coleta faltam" in pacote.completo({casos[0]: {}}, casos)
    assert "1 sobram" in pacote.completo(dict.fromkeys(casos + ["tests/test_b.py::t"], {}), casos)


def test_a_coleta_ignora_o_que_o_ambiente_acrescenta(monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k test_nenhum_nome_existe_assim")
    casos = pacote.coletados()
    assert "tests/test_pacote_gerado.py::test_a_coleta_ignora_o_que_o_ambiente_acrescenta" in casos
    assert len(casos) > 100


def test_nenhuma_execucao_fica_fora_da_normalizacao(gerado) -> None:
    """RVB4-2-01: toda chave de instante ou execução do pacote está num caminho que a comparação tira."""
    def chaves(no, caminho=()):
        if isinstance(no, dict):
            for k, v in no.items():
                yield caminho + (k,)
                if k not in ("relations", "meta", "columns"):          # nomes de dado, não de estrutura
                    yield from chaves(v, caminho + (k,))
    execucao = {c for c in chaves(gerado) if c[-1].endswith(("generated_at", "invocation_id")) or c[-1] in
                ("executed_at", "run_id", "same_invocation_as_manifest", "tree_dirty_at_generation")}
    conhecidos = {tuple(c) for c in pacote.EXECUCAO_DO_PACOTE}
    resto = {c for c in execucao if c not in conhecidos and not (c[0] in ("tests", "checks") and c[2] == "result")}
    assert resto == set()
    assert ("lineage", "manifest_generated_at") in execucao


@pytest.mark.integracao
def test_um_build_equivalente_nao_atrasa_o_pacote_e_um_grafo_novo_atrasa() -> None:
    """RVB4-2-01: duas montagens reais que só diferem na execução são iguais para o `--check`."""
    if not (pacote.MANIFEST.exists() and pacote.RUN_RESULTS.exists()):
        pytest.skip("sem os artefatos do dbt")
    import copy

    from mvp_ed1.models import sensitivity

    manifest, derivacao = sensitivity.load()
    run = json.loads(pacote.RUN_RESULTS.read_text(encoding="utf-8"))
    antes = pacote.montar(manifest, derivacao, run)
    outro_manifest, outro_run = copy.deepcopy(manifest), copy.deepcopy(run)
    for artefato in (outro_manifest, outro_run):
        artefato["metadata"]["generated_at"], artefato["metadata"]["invocation_id"] = "2030-01-01T00:00:00Z", "outra"
    for r in outro_run["results"]:
        for passo in r.get("timing") or []:
            passo["completed_at"] = "2030-01-01T00:00:01Z"
    depois = pacote.montar(outro_manifest, derivacao, outro_run)
    assert depois["lineage"]["manifest_generated_at"] != antes["lineage"]["manifest_generated_at"]
    assert pacote.diferencas(antes, depois) == []
    relacao = next(iter(outro_manifest["nodes"].values()))
    relacao["description"] = "Descrição de outra declaração."
    assert pacote.diferencas(antes, pacote.montar(outro_manifest, derivacao, outro_run)) != []


def test_o_pacote_vazio_ou_recortado_nao_e_publicavel() -> None:
    """RVB4-3-01: `checks: {}` é só o estado intermediário; o `check-offline` e a 5ª etapa o recusam."""
    casos = ["tests/test_a.py::test_x", "tests/test_a.py::test_y"]
    cheio = {"checks": dict.fromkeys(casos, {})}
    assert pacote.faltas_no_pytest(cheio, casos) is None
    assert "vazio" in pacote.faltas_no_pytest({"checks": {}}, casos)
    assert "faltam" in pacote.faltas_no_pytest({"checks": {casos[0]: {}}}, casos)
