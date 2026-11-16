"""Domínio de pagamentos — 4 tabelas.

As invariantes 3 e 4 — captura não excede a autorização, reembolso não excede a
captura — atravessam linhas e por isso o modelo não as expressa como `CHECK`.
Aqui elas são garantidas por construção: a captura é derivada do valor
autorizado, e o reembolso, do valor capturado. Nenhum dos dois é sorteado
livremente.

O estado do pagamento acompanha o do pedido. Pedido entregue com pagamento
`failed` passa em toda constraint do banco e é absurdo comercial — o tipo de
incoerência que só a reconciliação da Etapa 6 encontraria.
"""

from __future__ import annotations

from decimal import Decimal

from mvp_ed1.generator.dataset import Dataset
from mvp_ed1.generator.engine import Motor
from mvp_ed1.generator.rng import cobrir, dinheiro

#: Meios em que parcelamento não existe.
_A_VISTA = ("pix", "boleto", "debit_card")


def meios(motor: Motor, dados: Dataset) -> None:
    n = motor.linhas("payment_methods")
    dados.guardar("payment_methods", motor.preencher("payment_methods", [{} for _ in range(n)]))


def fluxo(motor: Motor, dados: Dataset) -> None:
    metodos = dados["payment_methods"]
    fonte = motor.fonte("payments")
    processo = motor.config.tabelas["payments"].processo
    parcelas_pesos = {int(k): v for k, v in processo["parcelas_pesos"].items()}

    pagamentos: list[dict] = []
    transacoes: list[dict] = []
    reembolsos: list[dict] = []

    # Os dois desfechos do pedido em aberto aparecem em qualquer fator e
    # semente (F29): sorteados meio a meio, um deles some quando os pedidos em
    # aberto são poucos — o perfil do legado não tinha autorização `pending`.
    em_aberto = {
        "restam": sum(1 for pedido in dados["orders"] if _em_aberto(pedido)),
        "faltam": ["pending", "authorized"],
    }

    for pedido in dados["orders"]:
        caminho = pedido["__caminho"]
        momentos = pedido["__momentos"]
        pago = "paid" in caminho
        valor = pedido["total_amount"]
        metodo = fonte.escolha(metodos)
        parcelas = 1 if metodo["method_type"] in _A_VISTA else fonte.ponderada(parcelas_pesos)

        # Tentativa recusada antes da que deu certo: é a origem das 1,05
        # intenções de pagamento por pedido da proporção de referência.
        if pago and fonte.chance(processo["nova_tentativa_apos_falha"]):
            recusada = _pagamento(pedido, metodo, valor, parcelas, "failed", None, None)
            pagamentos.append(recusada)
            transacoes.append(
                _transacao(recusada, "authorization", "failed", valor, momentos["pending"], fonte)
            )

        estado, autorizado_em, capturado_em = _desfecho(
            pedido, caminho, momentos, fonte, em_aberto
        )
        pagamento = _pagamento(pedido, metodo, valor, parcelas, estado, autorizado_em, capturado_em)
        pagamentos.append(pagamento)

        if estado == "failed":
            transacoes.append(
                _transacao(pagamento, "authorization", "failed", valor, momentos["pending"], fonte)
            )
            continue
        if estado == "pending":
            transacoes.append(
                _transacao(pagamento, "authorization", "pending", valor, momentos["pending"], fonte)
            )
            continue

        autorizado = valor
        transacoes.append(
            _transacao(pagamento, "authorization", "succeeded", autorizado, autorizado_em, fonte)
        )
        if estado == "cancelled":
            # Autorização sem captura é desfeita, não capturada: é o que o tipo
            # `void` existe para registrar.
            transacoes.append(
                _transacao(pagamento, "void", "succeeded", autorizado, momentos["cancelled"], fonte)
            )
            continue
        if estado == "authorized":
            continue

        # Invariante 3: a captura nunca excede o autorizado.
        capturado = (
            dinheiro(autorizado * Decimal(str(fonte.rng.uniform(0.85, 0.99))))
            if fonte.chance(0.03)
            else autorizado
        )
        captura = _transacao(pagamento, "capture", "succeeded", capturado, capturado_em, fonte)
        transacoes.append(captura)

        if estado == "refunded":
            _reembolsar(motor, fonte, pedido, captura, capturado, transacoes, reembolsos)

    dados.guardar("payments", motor.preencher("payments", pagamentos))
    _codigos_de_retorno(motor, transacoes)
    for transacao in transacoes:
        transacao["payment_id"] = transacao.pop("__pagamento")["id"]
    dados.guardar("payment_transactions", motor.preencher("payment_transactions", transacoes))
    for reembolso in reembolsos:
        reembolso["payment_transaction_id"] = reembolso.pop("__transacao")["id"]
    dados.guardar("refunds", motor.preencher("refunds", reembolsos))


def _em_aberto(pedido: dict) -> bool:
    """Pedido que ainda não foi pago nem encerrado: o pagamento dele está em curso."""
    return "paid" not in pedido["__caminho"] and pedido["status"] not in ("returned", "cancelled")


def _desfecho(pedido: dict, caminho: tuple[str, ...], momentos: dict, fonte, em_aberto: dict):
    """Estado do pagamento e as duas datas que a `CHECK` do modelo relaciona.

    `em_aberto` leva a cobertura garantida dos pedidos em aberto: quantos ainda
    restam e que desfechos ainda não saíram. O sorteio é o de sempre; só quando
    os pedidos que restam são tantos quantos os desfechos que faltam é que o
    sorteado cede o lugar ao que falta — como a reabertura garantida do
    atendimento, sem mexer na proporção em volume que valha medir.
    """
    final = pedido["status"]
    if final == "returned":
        return "refunded", momentos["pending"], momentos["paid"]
    if "paid" in caminho and final != "cancelled":
        return "captured", momentos["pending"], momentos["paid"]
    if final == "cancelled":
        if "paid" in caminho:
            return "cancelled", momentos["pending"], None
        return ("cancelled" if fonte.chance(0.5) else "failed"), momentos["pending"], None
    estado = "pending" if fonte.chance(0.5) else "authorized"
    faltam = em_aberto["faltam"]
    if estado not in faltam and faltam and em_aberto["restam"] <= len(faltam):
        estado = faltam[0]
    if estado in faltam:
        faltam.remove(estado)
    em_aberto["restam"] -= 1
    return estado, momentos["pending"], None


def _pagamento(pedido, metodo, valor, parcelas, estado, autorizado_em, capturado_em) -> dict:
    return {
        "order_id": pedido["id"],
        "payment_method_id": metodo["id"],
        "status": estado,
        "amount": valor,
        "installments": parcelas,
        # `CHECK captura_exige_autorizacao`: capturar sem autorizar é impossível.
        "authorized_at": autorizado_em if estado != "failed" else None,
        "captured_at": capturado_em,
        "created_at": pedido["placed_at"],
        "deleted_at": None,
    }


def _transacao(pagamento, tipo, resultado, valor, momento, fonte) -> dict:
    return {
        "__pagamento": pagamento,
        "transaction_type": tipo,
        "result": resultado,
        "amount": valor,
        "occurred_at": momento,
        "created_at": momento,
    }


def _codigos_de_retorno(motor: Motor, transacoes: list[dict]) -> None:
    """O código do adquirente segue o resultado — invariante 19 do Modelo de Dados §4.

    A aprovada e a pendente têm um código só; a recusada sorteia o motivo pelos
    pesos declarados, com a cobertura garantida quando há recusas que bastem:
    em fator pequeno, um motivo de peso 10 sumiria do dado.
    """
    mapa = motor.config.tabelas["payment_transactions"].processo["codigo_de_retorno"]
    fonte = motor.fonte("payment_transactions")
    motivos = {str(codigo): peso for codigo, peso in mapa["failed"].items()}
    recusadas = [t for t in transacoes if t["result"] == "failed"]
    sorteados = cobrir([fonte.ponderada(motivos) for _ in recusadas], sorted(motivos))
    for transacao, codigo in zip(recusadas, sorteados):
        transacao["gateway_response_code"] = codigo
    for transacao in transacoes:
        if transacao["result"] != "failed":
            transacao["gateway_response_code"] = str(mapa[transacao["result"]])


def _reembolsar(motor, fonte, pedido, captura, capturado, transacoes, reembolsos) -> None:
    """Reembolso total ou em duas parcelas — invariante 4 respeitada nas duas."""
    processo = motor.config.tabelas["refunds"].processo
    momento = pedido["__momentos"].get("returned", pedido["__fim_do_caminho"])
    if fonte.chance(processo["reembolso_parcial"]):
        primeira = dinheiro(capturado * Decimal(str(fonte.rng.uniform(0.3, 0.6))))
        valores = [primeira, dinheiro(capturado - primeira)]
    else:
        valores = [capturado]

    for parcela in valores:
        if parcela <= 0:
            continue
        transacoes.append(
            _transacao(captura["__pagamento"], "refund", "succeeded", parcela, momento, fonte)
        )
        reembolsos.append(
            {
                "__transacao": captura,
                "amount": parcela,
                "refunded_at": momento,
                "created_at": momento,
                "deleted_at": None,
            }
        )
