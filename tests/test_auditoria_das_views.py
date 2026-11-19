"""A auditoria das 16 views de `consumption` (Bloco 1b do plano da base dos consumidores).

── O que se prova ──────────────────────────────────────────────────────────
Cada view é comparada, linha a linha, com uma **referência** escrita a partir da
definição do glossário e das Perguntas de Negócio, e não do SQL da view: os
arquivos de `tests/auditoria/`, um por view. A comparação é de multiconjunto
(`except all` nos dois sentidos), numa transação `REPEATABLE READ READ ONLY`,
para a view e a referência lerem o mesmo corte — a P12 depende do caminho
quente, que muda entre duas leituras.

Os três critérios da etapa 2.11 do `bi-como-codigo` entram assim:

* **não aditividade:** a referência agrega numerador e denominador no grão de
  cada um e só então divide, com outra construção (por pedido, por junção de
  intervalo); uma razão com denominador recortado diverge dela;
* **saldo que depende do tempo:** a P11 (média do trimestre, nada posterior) e a
  P12 (livro inteiro, mais o caminho quente) têm referência própria;
* **população recortada:** `tests/auditoria/populacao/` compara o total de cada
  view com a população elegível na camada responsável (`trusted`), porque
  recalcular sobre a fato conservaria o que ela perdeu.

── A contraprova ────────────────────────────────────────────────────────────
Uma referência que só concorda com a view corrigida não prova que acharia o
defeito. `tests/auditoria/contraprova/` guarda o SQL compilado das versões
defeituosas do F1 e do F2 (do *commit* `32397cc`) e das duas que a própria auditoria
corrigiu (a P04 e a P14), e o teste exige que a
referência **discorde** delas, rodando-as como consulta somente leitura.

── Limite declarado ─────────────────────────────────────────────────────────
O autor das referências leu o SQL das views antes de escrevê-las (o passo 1 do
bloco levou para o glossário as regras que só existiam lá, o F9). A
independência é de construção e de fonte, não de autoria. Nas referências da
P05, P07, P13 e P14 a construção é quase a da view (as mesmas fatos, os mesmos
recortes, a mesma agregação): elas provam a igualdade e o critério de valor,
mas o critério de população delas fica com as conferências de
`tests/auditoria/populacao/` (P07, P13 e P14) e, na P05, só com a da receita
(P01), que usa a mesma fato (RVB1b-1-05).
"""

from __future__ import annotations

import pathlib

import pytest
import yaml
from sqlalchemy import create_engine, text

from mvp_ed1.db import WAREHOUSE, database_url

pytestmark = pytest.mark.integracao

RAIZ = pathlib.Path(__file__).resolve().parents[1]
AUDITORIA = RAIZ / "tests" / "auditoria"
VIEWS = sorted(p.stem for p in (RAIZ / "dbt" / "models" / "consumption").glob("*.sql"))


def _variaveis() -> dict[str, int]:
    projeto = yaml.safe_load((RAIZ / "dbt" / "dbt_project.yml").read_text(encoding="utf-8"))
    return {
        # O ponto de reposição da P12 (ADR-0057): a referência o calcula dos três parâmetros, sem ler o modelo.
        "prazo_de_reposicao": int(projeto["vars"]["reorder_lead_time_days"]),
        "margem_de_seguranca": int(projeto["vars"]["reorder_safety_days"]),
        "janela_do_ponto": int(projeto["vars"]["reorder_demand_window_days"]),
        "janela_de_cobertura": int(projeto["vars"]["cover_window_days"]),
    }


def _sql(caminho: pathlib.Path) -> str:
    return caminho.read_text(encoding="utf-8").strip().rstrip(";")


@pytest.fixture(scope="module")
def engine():
    motor = create_engine(database_url(WAREHOUSE))
    try:
        with motor.connect() as conexao:
            conexao.execute(text("select 1 from consumption.monthly_revenue_by_channel_and_category limit 1"))
    except Exception as erro:  # pragma: no cover — depende do ambiente
        motor.dispose()
        pytest.skip(f"armazém sem as views de consumo: {erro}")
    yield motor
    motor.dispose()


def _corte(motor):
    """Uma conexão numa transação de corte consistente e somente leitura."""
    conexao = motor.connect()
    conexao.execute(text("begin transaction isolation level repeatable read read only"))
    return conexao


def _colunas(conexao, view: str) -> list[str]:
    return [
        linha[0]
        for linha in conexao.execute(
            text(
                "select column_name from information_schema.columns"
                " where table_schema = 'consumption' and table_name = :v order by ordinal_position"
            ),
            {"v": view},
        )
    ]


def _diferencas(conexao, colunas: list[str], esquerda: str, direita: str) -> tuple[int, int, list]:
    lista = ", ".join(colunas)
    so_esquerda = f"select {lista} from ({esquerda}) e except all select {lista} from ({direita}) d"
    so_direita = f"select {lista} from ({direita}) d except all select {lista} from ({esquerda}) e"
    parametros = _variaveis()
    a = conexao.execute(text(f"select count(*) from ({so_esquerda}) x"), parametros).scalar_one()
    b = conexao.execute(text(f"select count(*) from ({so_direita}) x"), parametros).scalar_one()
    amostra = [tuple(l) for l in conexao.execute(text(f"{so_esquerda} limit 3"), parametros)]
    return a, b, amostra


def test_toda_view_tem_referencia() -> None:
    referencias = {p.stem for p in AUDITORIA.glob("*.sql")}
    assert referencias == set(VIEWS), (
        f"views sem referência: {sorted(set(VIEWS) - referencias)}; "
        f"referências sem view: {sorted(referencias - set(VIEWS))}"
    )


@pytest.mark.parametrize("view", VIEWS)
def test_a_view_confere_com_a_referencia(engine, view: str) -> None:
    conexao = _corte(engine)
    try:
        colunas = _colunas(conexao, view)
        so_view, so_referencia, amostra = _diferencas(
            conexao, colunas, f"select * from consumption.{view}", _sql(AUDITORIA / f"{view}.sql")
        )
    finally:
        conexao.execute(text("rollback"))
        conexao.close()
    assert (so_view, so_referencia) == (0, 0), (
        f"{view}: {so_view} linha(s) só na view, {so_referencia} só na referência; amostra da view: {amostra}"
    )


POPULACOES = sorted(p.stem for p in (AUDITORIA / "populacao").glob("*.sql"))


@pytest.mark.parametrize("verificacao", POPULACOES)
def test_a_populacao_confere_com_a_camada_responsavel(engine, verificacao: str) -> None:
    """Cada arquivo devolve as linhas em que a view e a camada responsável divergem."""
    conexao = _corte(engine)
    try:
        linhas = [tuple(l) for l in conexao.execute(text(_sql(AUDITORIA / "populacao" / f"{verificacao}.sql")))]
    finally:
        conexao.execute(text("rollback"))
        conexao.close()
    assert linhas == [], f"{verificacao}: {linhas[:5]}"


CONTRAPROVAS = {
    # versão defeituosa → view cuja referência tem de discordar dela
    "f1_support_tickets_per_hundred_orders_32397cc": "support_tickets_per_hundred_orders",
    "f2_inventory_turnover_by_sku_and_warehouse_32397cc": "inventory_turnover_by_sku_and_warehouse",
    # a auditoria achou o padrão da D66 nestas duas (F17 e F18 dos Achados)
    "aud_order_to_delivery_time_by_region_f4ab54a": "order_to_delivery_time_by_region",
    "aud_new_and_repeat_customers_by_month_f4ab54a": "new_and_repeat_customers_by_month",
}


@pytest.mark.parametrize("defeituosa", sorted(CONTRAPROVAS))
def test_a_referencia_acusa_a_versao_defeituosa(engine, defeituosa: str) -> None:
    view = CONTRAPROVAS[defeituosa]
    conexao = _corte(engine)
    try:
        antiga = _sql(AUDITORIA / "contraprova" / f"{defeituosa}.sql")
        colunas_antigas = [
            c.name for c in conexao.execute(text(f"select * from ({antiga}) a limit 0")).cursor.description
        ]
        colunas = [c for c in colunas_antigas if c in set(_colunas(conexao, view))]
        so_antiga, so_referencia, _ = _diferencas(conexao, colunas, antiga, _sql(AUDITORIA / f"{view}.sql"))
    finally:
        conexao.execute(text("rollback"))
        conexao.close()
    assert so_antiga + so_referencia > 0, f"a referência de {view} não acusa a versão defeituosa"


def test_a_contraprova_do_f1_acusa_o_denominador(engine) -> None:
    """A diferença do F1 é no denominador, não só no agrupamento (RVB1b-1-02).

    A versão defeituosa agrupava pela chave do canal de cada origem, e por isso tinha linhas a mais.
    Uma diferença de agrupamento não prova que a referência pegaria o denominador errado: aqui, os
    denominadores da versão antiga, reduzidos a mês × canal pelo nome, têm de discordar dos da
    referência em algum mês e canal com chamado.
    """
    antiga = _sql(AUDITORIA / "contraprova" / "f1_support_tickets_per_hundred_orders_32397cc.sql")
    referencia = _sql(AUDITORIA / "support_tickets_per_hundred_orders.sql")
    conexao = _corte(engine)
    try:
        divergentes = conexao.execute(
            text(
                f"""
                with velho as (
                    select year_month, sales_channel_name, max(channel_order_count) as d
                    from ({antiga}) a group by 1, 2
                ),
                novo as (
                    select year_month, sales_channel_name, max(channel_order_count) as d
                    from ({referencia}) r group by 1, 2
                )
                select count(*) from velho join novo using (year_month, sales_channel_name)
                where velho.d is distinct from novo.d
                """
            )
        ).scalar_one()
    finally:
        conexao.execute(text("rollback"))
        conexao.close()
    assert divergentes > 0

