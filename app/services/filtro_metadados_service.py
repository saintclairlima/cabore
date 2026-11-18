import math
from typing import Any, Dict, Optional

from sqlalchemy import Numeric, and_, case, cast, false, func, not_, or_, true



OPERADORES_FILTRO_METADADOS = {
    "$eq", "$ne", "$in", "$nin", "$gt", "$gte", "$lt", "$lte"
}


def construir_filtro_metadados(coluna, filtros: Optional[Dict[str, Any]]):
    """
    Constrói expressões SQLAlchemy para filtros recursivos sobre JSONB.

    Operadores suportados: $eq, $ne, $in, $nin, $gt, $gte, $lt, $lte.

    Igualdade e pertencimento utilizam contenção JSONB (@>). Comparações relacionais utilizam valores numéricos JSONB.
    Campos e condições diferentes são combinados com AND.
    """

    if filtros is None:
        return None

    if not isinstance(filtros, dict):
        raise ValueError("filtro_metadados deve ser um objeto JSON.")

    def construir_objeto_aninhado(caminho, valor):
        """
        Constrói um objeto JSON com base em um caminho.

        Exemplo:
            caminho = ["documento", "rotulo"]
            valor = "regimento_al"

        Resultado:
            {"documento": {"rotulo": "regimento_al"}}
        """
        resultado = valor

        for chave in reversed(caminho):
            resultado = {chave: resultado}

        return resultado

    def obter_expressao_jsonb(caminho):
        """
        Obtém a expressão SQLAlchemy correspondente a um caminho JSONB.
        """
        expressao = coluna

        for chave in caminho:
            expressao = expressao[chave]

        return expressao

    def validar_numero(valor, operador, caminho):
        """
        Valida os operandos dos operadores relacionais.
        """
        if (
            isinstance(valor, bool)
            or not isinstance(valor, (int, float))
            or not math.isfinite(valor)
        ):
            raise ValueError(
                f"O operador {operador} do campo "
                f"'{'.'.join(caminho)}' exige um valor numérico finito."
            )

    def construir_operador(caminho, operador, operando):
        """
        Constrói uma condição SQLAlchemy para um operador.
        """
        objeto = lambda valor: construir_objeto_aninhado(caminho, valor)
        if operador == "$eq": return coluna.contains(objeto(operando))
        if operador == "$ne": return not_(coluna.contains(objeto(operando)))
        if operador in {"$in", "$nin"}:
            if not isinstance(operando, list):
                raise ValueError(f"O operador {operador} do campo '{'.'.join(caminho)}' deve receber uma lista.")
            condicoes = [coluna.contains(objeto(item)) for item in operando]
            if operador == "$in": return or_(*condicoes) if condicoes else false()
            return (
                and_(*[not_(condicao) for condicao in condicoes])
                if condicoes else true()
            )

        if operador in {"$gt", "$gte", "$lt", "$lte"}:
            validar_numero(operando, operador, caminho)
            valor_json = obter_expressao_jsonb(caminho)
            valor_numerico = case(
                (
                    func.jsonb_typeof(valor_json) == "number",
                    cast(valor_json.astext, Numeric)
                ),
                else_=None
            )
            comparadores = {
                "$gt": valor_numerico > operando,
                "$gte": valor_numerico >= operando,
                "$lt": valor_numerico < operando,
                "$lte": valor_numerico <= operando,
            }

            return comparadores[operador]

        raise ValueError(
            f"Operador '{operador}' não suportado no campo '{'.'.join(caminho)}'. "
            f"Operadores disponíveis: {', '.join(sorted(OPERADORES_FILTRO_METADADOS))}."
        )

    def construir_condicoes(dados, caminho=()):
        if not isinstance(dados, dict):
            raise ValueError(f"Era esperado um objeto JSON no caminho '{'.'.join(caminho)}'.")

        condicoes = []

        for chave, valor in dados.items():
            if not isinstance(chave, str) or not chave:
                raise ValueError("As chaves de filtro_metadados devem ser strings não vazias.")
            if chave.startswith("$"):
                raise ValueError(f"Operador '{chave}' não pode ser utilizado sem um campo.")
            caminho_atual = (*caminho, chave)
            if isinstance(valor, dict):
                chaves_operadores = {k for k in valor if isinstance(k, str) and k.startswith("$")}
                if chaves_operadores:
                    if len(chaves_operadores) != len(valor):
                        raise ValueError(f"O campo '{'.'.join(caminho_atual)}' não pode misturar operadores e propriedades.")
                    for operador, operando in valor.items():
                        condicoes.append(construir_operador(caminho_atual, operador, operando))
                elif valor:
                    condicoes.extend(construir_condicoes(valor, caminho_atual))
                else:
                    condicoes.append(coluna.contains(construir_objeto_aninhado(caminho_atual, {})))
            else:
                condicoes.append(coluna.contains(construir_objeto_aninhado(caminho_atual, valor)))

        return condicoes
    
    condicoes = construir_condicoes(filtros)
    return and_(*condicoes) if condicoes else None
