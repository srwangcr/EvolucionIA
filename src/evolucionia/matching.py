"""
Motor de matching de órdenes con Polars (vectorizado).
Reemplaza los loops O(n²) por operaciones DataFrame.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from .models import Agent


@dataclass
class MatchResult:
    """Resultado de una ejecución de matching."""
    
    transactions: list[dict[str, int | float]]
    matched_buyers: list[int]
    matched_sellers: list[int]
    avg_price: float
    volume: int


class PolarsMatcher:
    """
    Matcher de órdenes usando Polars para operaciones vectorizadas.
    """

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self._seed = seed

    def match(
        self,
        buyers: list[Agent],
        sellers: list[Agent],
        price: float,
        max_quantity: int = 1,
    ) -> MatchResult:
        """Empareja compradores y vendedores usando Polars."""
        if not buyers or not sellers:
            return MatchResult([], [], [], price, 0)

        # 1. Convertir a DataFrames
        buyers_df = self._agents_to_df(buyers)
        sellers_df = self._agents_to_df(sellers)

        # 2. Filtrar compradores con balance suficiente
        buyers_df = buyers_df.filter(pl.col("balance") >= price)

        # 3. Filtrar vendedores con inventario > 0
        sellers_df = sellers_df.filter(pl.col("inventory") > 0)

        if buyers_df.is_empty() or sellers_df.is_empty():
            return MatchResult([], [], [], price, 0)

        # 4. Orden aleatorio para fairness
        buyers_df = buyers_df.with_columns(
            pl.Series("_order", [self.rng.random() for _ in range(buyers_df.height)])
        ).sort("_order")
        
        sellers_df = sellers_df.with_columns(
            pl.Series("_order", [self.rng.random() for _ in range(sellers_df.height)])
        ).sort("_order")

        # 5. Matching secuencial por posición
        max_tx = min(buyers_df.height, sellers_df.height)
        
        if max_tx == 0:
            return MatchResult([], [], [], price, 0)

        # Asignar índices de transacción
        buyers_tx = buyers_df.head(max_tx).with_columns(
            pl.int_range(0, max_tx).alias("tx_idx")
        )
        sellers_tx = sellers_df.head(max_tx).with_columns(
            pl.int_range(0, max_tx).alias("tx_idx")
        )

        # Join por índice de transacción
        matches = buyers_tx.join(
            sellers_tx,
            on="tx_idx",
            how="inner",
            suffix="_seller"
        )

        if matches.is_empty():
            return MatchResult([], [], [], price, 0)

        # 6. Construir transacciones
        transactions = []
        matched_buyers = []
        matched_sellers = []

        for row in matches.rows(named=True):
            tx = {
                "buyer_id": row["agent_id"],
                "seller_id": row["agent_id_seller"],
                "resource": "ore",
                "price": round(price, 4),
                "quantity": max_quantity,
            }
            transactions.append(tx)
            matched_buyers.append(row["agent_id"])
            matched_sellers.append(row["agent_id_seller"])

        return MatchResult(
            transactions=transactions,
            matched_buyers=matched_buyers,
            matched_sellers=matched_sellers,
            avg_price=price,
            volume=len(transactions),
        )

    def _agents_to_df(self, agents: list[Agent]) -> pl.DataFrame:
        """Convierte lista de agentes a DataFrame Polars."""
        return pl.DataFrame({
            "agent_id": [a.agent_id for a in agents],
            "balance": [a.balance for a in agents],
            "inventory": [a.inventory for a in agents],
            "energy": [a.energy for a in agents],
            "species": [a.species.value for a in agents],
        })


class HybridMatcher:
    """
    Matcher híbrido: Polars para lotes grandes, Python para lotes pequeños.
    """
    
    def __init__(self, threshold: int = 50, seed: int | None = None):
        self.polars = PolarsMatcher(seed)
        self.threshold = threshold
        self.rng = random.Random(seed)

    def match(
        self,
        buyers: list[Agent],
        sellers: list[Agent],
        price: float,
        max_quantity: int = 1,
    ) -> MatchResult:
        """Elige método según tamaño."""
        # ⬇️ LOGS PARA DIAGNÓSTICO
        print(f"🔍 MATCH: {len(buyers)} buyers, {len(sellers)} sellers, threshold={self.threshold}")
        
        if len(buyers) <= self.threshold or len(sellers) <= self.threshold:
            print(f"🐍 Usando Python fallback")
            return self._python_match(buyers, sellers, price, max_quantity)
        
        print(f"⚡ Usando Polars vectorizado")
        return self.polars.match(buyers, sellers, price, max_quantity)

    def _python_match(
        self,
        buyers: list[Agent],
        sellers: list[Agent],
        price: float,
        max_quantity: int = 1,
    ) -> MatchResult:
        """Matching en Python puro (fallback)."""
        buyer_pool = buyers[:]
        seller_pool = sellers[:]
        
        self.rng.shuffle(buyer_pool)
        self.rng.shuffle(seller_pool)

        transactions = []
        matched_buyers = []
        matched_sellers = []

        for buyer in buyer_pool:
            # Buscar vendedor con inventario
            seller = None
            for s in seller_pool:
                if s.agent_id != buyer.agent_id and s.inventory > 0:
                    seller = s
                    break
            
            if seller is None:
                continue
                
            if buyer.balance < price:
                continue

            # Ejecutar transacción
            buyer.balance -= price
            buyer.inventory += max_quantity
            seller.balance += price
            seller.inventory -= max_quantity

            transactions.append({
                "buyer_id": buyer.agent_id,
                "seller_id": seller.agent_id,
                "resource": "ore",
                "price": round(price, 4),
                "quantity": max_quantity,
            })
            matched_buyers.append(buyer.agent_id)
            matched_sellers.append(seller.agent_id)

            if seller.inventory <= 0:
                seller_pool = [s for s in seller_pool if s.agent_id != seller.agent_id]

        return MatchResult(
            transactions=transactions,
            matched_buyers=matched_buyers,
            matched_sellers=matched_sellers,
            avg_price=price if transactions else 0.0,
            volume=len(transactions),
        )