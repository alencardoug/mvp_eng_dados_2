"""Domínio de atendimento — 3 tabelas.

Chamado não nasce de sorteio: nasce de um fato que já está no banco — a entrega
que atrasou, o pagamento que falhou, o pedido que foi devolvido. É o que torna
`fact_support_ticket_event` da Etapa 9 cruzável com as outras fatos em vez de
ser ruído correlacionado com nada.
"""

from __future__ import annotations

import datetime as dt

from mvp_ed1.generator.dataset import Dataset
from mvp_ed1.generator.engine import Motor
from mvp_ed1.generator.rng import cobrir, repartir

#: Categorias na ordem em que o modelo as aceita; as primeiras linhas levam uma
#: cada, e o resto é decidido pelo fato que originou o chamado.
_CATEGORIAS = ("delivery", "payment", "product", "return", "account", "other")
_ESTADOS = ("open", "in_progress", "waiting_customer", "resolved", "closed")
_ENCERRADOS = ("resolved", "closed")

#: Da abertura ao fim do atendimento que resolve, e da resolução à reabertura, em horas.
_RESOLUCAO_H = (2, 400)
_REABERTURA_H = (1, 240)

#: Teto de mensagens e mudanças de estado por chamado, além dos eventos que o
#: estado dele exige.
_OPCIONAIS_MAXIMO = 5


def agentes(motor: Motor, dados: Dataset) -> None:
    n = motor.linhas("support_agents")
    dados.guardar("support_agents", motor.preencher("support_agents", [{} for _ in range(n)]))


def chamados(motor: Motor, dados: Dataset) -> None:
    fonte = motor.fonte("support_tickets")
    processo = motor.config.tabelas["support_tickets"].processo
    agentes_linhas = dados["support_agents"]
    total = motor.linhas("support_tickets")

    fatos = _fatos(motor, dados)
    esqueletos: list[dict] = []
    for indice in range(total):
        fato = fatos[indice % len(fatos)] if fatos else None
        sem_pedido = fonte.chance(processo["sem_pedido_associado"]) or fato is None
        categoria = _CATEGORIAS[indice] if indice < len(_CATEGORIAS) else (
            "account" if sem_pedido else fato["categoria"]
        )
        estado = _ESTADOS[indice] if indice < len(_ESTADOS) else fonte.ponderada(
            {"closed": 46, "resolved": 24, "in_progress": 14, "waiting_customer": 10, "open": 6}
        )
        if sem_pedido:
            cliente = fonte.escolha(dados["customers"])
            aberto = motor.relogio.sazonal(fonte)
            pedido_id = remessa_id = None
        else:
            cliente, aberto = fato["cliente_id"], fato["momento"]
            pedido_id, remessa_id = fato["order_id"], fato["shipment_id"]
            cliente = {"id": cliente}
        esqueletos.append(
            {
                "customer_id": cliente["id"],
                "order_id": pedido_id,
                "shipment_id": remessa_id,
                "assigned_agent_id": (
                    fonte.escolha(agentes_linhas)["id"] if estado != "open" else None
                ),
                "category": categoria,
                "status": estado,
                "opened_at": aberto,
                # Só o `closed` tem data de fechamento (Q24): a resolução do
                # `resolved` é o evento `resolved` do livro, não esta coluna.
                "closed_at": (
                    motor.relogio.depois(aberto, fonte, *_RESOLUCAO_H) if estado == "closed" else None
                ),
                "deleted_at": None,
            }
        )
    chamados_linhas = dados.guardar("support_tickets", motor.preencher("support_tickets", esqueletos))
    _eventos(motor, dados, chamados_linhas)


def _fatos(motor: Motor, dados: Dataset) -> list[dict]:
    """Os acontecimentos que geram atendimento, na ordem em que ocorreram."""
    fatos: list[dict] = []
    pedidos = {linha["id"]: linha for linha in dados["orders"]}

    for remessa in dados["shipments"]:
        pedido = pedidos[remessa["order_id"]]
        atrasada = (
            remessa["delivered_at"] is not None
            and remessa["estimated_delivery_at"] is not None
            and remessa["delivered_at"] > remessa["estimated_delivery_at"]
        )
        if not atrasada and remessa["status"] not in ("lost", "returned"):
            continue
        fatos.append(
            {
                "categoria": "return" if remessa["status"] == "returned" else "delivery",
                "cliente_id": pedido["customer_id"],
                "order_id": pedido["id"],
                "shipment_id": remessa["id"],
                "momento": remessa["delivered_at"] or remessa["created_at"],
            }
        )

    for pagamento in dados["payments"]:
        if pagamento["status"] not in ("failed", "cancelled"):
            continue
        pedido = pedidos[pagamento["order_id"]]
        fatos.append(
            {
                "categoria": "payment",
                "cliente_id": pedido["customer_id"],
                "order_id": pedido["id"],
                "shipment_id": None,
                "momento": pedido["placed_at"],
            }
        )

    for pedido in dados["orders"]:
        if pedido["status"] == "returned":
            fatos.append(
                {
                    "categoria": "product",
                    "cliente_id": pedido["customer_id"],
                    "order_id": pedido["id"],
                    "shipment_id": None,
                    "momento": pedido["__fim_do_caminho"],
                }
            )
    fatos.sort(key=lambda f: (f["momento"], f["order_id"]))
    return fatos


def _eventos(motor: Motor, dados: Dataset, chamados_linhas: list[dict]) -> None:
    """O livro de cada chamado, coerente com o estado em que ele parou.

    Invariante 17 do Modelo de Dados §4: todo chamado `resolved` ou `closed`
    tem o evento `resolved`, e todo `reopened` vem depois de um. Por isso os
    eventos **obrigatórios** de todos os chamados são levantados primeiro, e só
    o que sobra do orçamento da tabela é repartido em opcionais — cortar a
    lista pronta no tamanho sorteado tirava justamente a resolução dos chamados
    de dois eventos, e repartir o orçamento antes de conhecer os obrigatórios
    o estourava: no piso, 16 eventos para 6 pedidos, e nenhum opcional.
    """
    fonte = motor.fonte("ticket_events")

    # O primeiro chamado em andamento que couber é sempre reaberto: sem isso
    # `reopened` depende de 25% de 14% dos chamados e desaparece em fator pequeno.
    reabertura_pendente = True

    planos: list[tuple[dict, list[str], list[str], bool, dt.datetime]] = []
    for chamado in chamados_linhas:
        aberto = chamado["opened_at"]
        iniciais = ["created"]
        if chamado["assigned_agent_id"]:
            iniciais.append("assigned")

        # Até quando vai o atendimento que termina em resolução. O chamado
        # fechado tem a data dele; o resolvido e o reaberto sorteiam a sua na
        # mesma faixa — usar o fim do período levaria a resolução a meses da
        # abertura. O que continua aberto se espalha até o fim, como antes.
        reaberto = False
        if chamado["status"] == "closed":
            horizonte = chamado["closed_at"]
        elif chamado["status"] == "resolved":
            horizonte = motor.relogio.depois(aberto, fonte, *_RESOLUCAO_H)
        elif chamado["status"] == "in_progress" and (reabertura_pendente or fonte.chance(0.25)):
            horizonte = motor.relogio.depois(aberto, fonte, *_RESOLUCAO_H)
            # Reabrir pede tempo depois da resolução: sem ele o chamado segue
            # em andamento sem as duas, e a reabertura garantida fica para o próximo.
            reaberto = horizonte < motor.fim
            if reaberto:
                reabertura_pendente = False
            else:
                horizonte = motor.fim
        else:
            horizonte = motor.fim

        finais = ["resolved"] if chamado["status"] in _ENCERRADOS or reaberto else []
        planos.append((chamado, iniciais, finais, reaberto, horizonte))

    # O que sobra do orçamento, depois dos obrigatórios, vira mensagem e mudança
    # de estado. Os dois tipos aparecem sempre que há lugar para os dois: é o
    # que o piso de `ticket_events` em `geracao.yml` garante.
    obrigatorios = sum(len(i) + len(f) + (1 if r else 0) for _, i, f, r, _ in planos)
    sobra = max(motor.linhas("ticket_events") - obrigatorios, 0)
    por_chamado = repartir(sobra, len(planos), fonte, minimo=0, maximo=_OPCIONAIS_MAXIMO)
    opcionais = cobrir(
        ["message" if fonte.chance(0.7) else "status_changed" for _ in range(sum(por_chamado))],
        ("message", "status_changed"),
    )

    esqueletos: list[dict] = []
    for (chamado, iniciais, finais, reaberto, horizonte), quantos in zip(planos, por_chamado):
        aberto = chamado["opened_at"]
        tipos = iniciais + [opcionais.pop() for _ in range(quantos)] + finais
        passo = max((horizonte - aberto) / len(tipos), dt.timedelta(minutes=15))
        momento = aberto
        for tipo in tipos:
            esqueletos.append(_evento(chamado, tipo, momento, fonte))
            ultimo = momento
            momento = min(momento + passo, motor.fim)
        if reaberto:
            esqueletos.append(
                _evento(chamado, "reopened", motor.relogio.depois(ultimo, fonte, *_REABERTURA_H), fonte)
            )
    dados.guardar("ticket_events", motor.preencher("ticket_events", esqueletos))


def _evento(chamado: dict, tipo: str, momento: dt.datetime, fonte) -> dict:
    return {
        "ticket_id": chamado["id"],
        "agent_id": chamado["assigned_agent_id"] if tipo != "created" and fonte.chance(0.8) else None,
        "event_type": tipo,
        "occurred_at": momento,
        "created_at": momento,
    }
