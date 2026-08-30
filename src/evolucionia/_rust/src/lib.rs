use pyo3::prelude::*;
use pyo3::types::PyAny;
use pyo3::IntoPyObjectExt;
use rand::prelude::*;
use rand::rngs::SmallRng;
use std::collections::HashMap;

// ============================================================
// ESTRUCTURAS DE DATOS
// ============================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Species {
    Miner,
    Speculator,
    Consumer,
}

impl From<&str> for Species {
    fn from(s: &str) -> Self {
        match s {
            "miner" => Species::Miner,
            "speculator" => Species::Speculator,
            "consumer" => Species::Consumer,
            _ => Species::Consumer,
        }
    }
}

impl From<Species> for String {
    fn from(s: Species) -> Self {
        match s {
            Species::Miner => "miner".to_string(),
            Species::Speculator => "speculator".to_string(),
            Species::Consumer => "consumer".to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Agent {
    pub agent_id: i32,
    pub species: Species,
    pub balance: f64,
    pub inventory: i32,
    pub energy: f64,
    pub buy_threshold: f64,
    pub sell_threshold: f64,
    pub production_rate: i32,
    pub risk_tolerance: f64,
    pub momentum_bias: f64,
    pub reproduction_drive: f64,
    pub alive: bool,
    pub generation: i32,
}

impl Agent {
    pub fn wealth(&self, price: f64) -> f64 {
        self.balance + (self.inventory as f64) * price
    }

    pub fn decide(&self, price: f64, trend: f64) -> Decision {
        match self.species {
            Species::Miner => self.decide_miner(price, trend),
            Species::Speculator => self.decide_speculator(price, trend),
            Species::Consumer => self.decide_consumer(price, trend),
        }
    }

    fn low_membership(&self, value: f64, threshold: f64) -> f64 {
        if threshold <= 0.0 {
            return 0.0;
        }
        (threshold - value).max(0.0).min(threshold) / threshold
    }

    fn high_membership(&self, value: f64, threshold: f64) -> f64 {
        if threshold <= 0.0 {
            return 0.0;
        }
        (value - threshold).max(0.0).min(threshold) / threshold
    }

    fn trend_up(&self, trend: f64, price: f64) -> f64 {
        if price <= 0.0 {
            return 0.0;
        }
        (trend / price).max(0.0).min(1.0)
    }

    fn trend_down(&self, trend: f64, price: f64) -> f64 {
        if price <= 0.0 {
            return 0.0;
        }
        ((-trend) / price).max(0.0).min(1.0)
    }

    fn decide_miner(&self, price: f64, trend: f64) -> Decision {
        let price_low = self.low_membership(price, self.buy_threshold);
        let price_high = self.high_membership(price, self.sell_threshold);
        let stock_high = self.high_membership(self.inventory as f64, 2.0);
        let energy_low = self.low_membership(self.energy, 10.0);
        let trend_up = self.trend_up(trend, price);

        let sell_score = 0.5 * stock_high + 0.3 * price_high + 0.2 * energy_low;
        let buy_score = 0.35 * price_low + 0.25 * trend_up + 0.4 * (1.0 - self.risk_tolerance);

        if sell_score >= 0.4 && self.inventory > 0 {
            return Decision::Sell;
        }
        if buy_score >= 0.55 && self.balance >= price {
            return Decision::Buy;
        }
        Decision::Hold
    }

    fn decide_speculator(&self, price: f64, trend: f64) -> Decision {
        let price_low = self.low_membership(price, self.buy_threshold);
        let price_high = self.high_membership(price, self.sell_threshold);
        let trend_up = self.trend_up(trend, price);
        let trend_down = self.trend_down(trend, price);

        let buy_score = 0.4 * price_low + 0.35 * trend_up * self.momentum_bias + 0.25 * (1.0 - self.risk_tolerance);
        let sell_score = 0.45 * price_high + 0.35 * trend_down * (1.25 - self.momentum_bias) + 0.2 * self.risk_tolerance;

        let can_buy = buy_score >= 0.48 && self.balance >= price;
        let can_sell = sell_score >= 0.48 && self.inventory > 0;

        if can_buy && can_sell {
            return Decision::Both;
        }
        if can_buy {
            return Decision::Buy;
        }
        if can_sell {
            return Decision::Sell;
        }
        Decision::Hold
    }

    fn decide_consumer(&self, price: f64, _trend: f64) -> Decision {
        let price_low = self.low_membership(price, self.buy_threshold);
        let stock_low = self.low_membership(self.inventory as f64, 3.0);
        let energy_low = self.low_membership(self.energy, 8.0);
        let buy_score = 0.45 * price_low + 0.35 * stock_low + 0.2 * energy_low;

        if buy_score >= 0.42 && self.balance >= price {
            return Decision::Buy;
        }
        Decision::Hold
    }

    pub fn evolve(&mut self, scarcity: f64) {
        match self.species {
            Species::Miner => {
                self.energy = (self.energy - scarcity * 0.15).max(0.0);
                self.production_rate = (self.production_rate as f64 / (0.8 * scarcity).max(0.8)).round() as i32;
                self.production_rate = self.production_rate.max(1);
                self.reproduction_drive = (self.reproduction_drive * (1.0 + (1.0 - scarcity) * 0.02)).max(0.05);
            }
            Species::Speculator => {
                self.buy_threshold = (self.buy_threshold * (1.0 + scarcity * 0.02)).max(0.5);
                self.sell_threshold = (self.sell_threshold * (1.0 + scarcity * 0.01)).max(self.buy_threshold + 0.1);
                self.momentum_bias = (self.momentum_bias * (1.0 + (scarcity - 1.0) * 0.03)).max(0.05).min(1.5);
            }
            Species::Consumer => {
                self.energy = (self.energy - scarcity * 0.15).max(0.0);
                self.risk_tolerance = (self.risk_tolerance * (1.0 + scarcity * 0.01)).max(0.05);
            }
        }
    }

    pub fn produce(&mut self, scarcity: f64) {
        if self.species == Species::Miner && self.energy > 0.0 {
            let produced = (self.production_rate as f64 / (0.75 * scarcity).max(0.75)).round() as i32;
            self.inventory += produced.max(1);
            self.energy = (self.energy - 1.25 * scarcity).max(0.0);
        } else if self.species == Species::Consumer {
            if self.inventory > 0 {
                self.inventory -= 2;
                self.energy = (self.energy + 3.0).min(20.0);
            } else {
                self.energy = (self.energy - 3.0 * scarcity).max(0.0);
            }
        } else {
            self.energy = (self.energy - 0.8 * scarcity).max(0.0);
        }

        if self.energy <= 0.0 && self.species != Species::Speculator && self.inventory <= 0 {
            self.alive = false;
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Buy,
    Sell,
    Both,
    Hold,
}

// ============================================================
// TRANSACCIÓN
// ============================================================

#[derive(Debug, Clone)]
pub struct Transaction {
    pub buyer_id: i32,
    pub seller_id: i32,
    pub price: f64,
    pub quantity: i32,
}

// ============================================================
// RESULTADO DE TICK (con transacciones)
// ============================================================

#[pyclass]
#[derive(Clone)]
pub struct TickResult {
    #[pyo3(get)]
    pub tick: i32,
    #[pyo3(get)]
    pub price: f64,
    #[pyo3(get)]
    pub transactions: i32,
    #[pyo3(get)]
    pub buyers: i32,
    #[pyo3(get)]
    pub sellers: i32,
    #[pyo3(get)]
    pub survivors: i32,
    #[pyo3(get)]
    pub tx_list: Vec<(i32, i32, f64, i32)>,
}

// ============================================================
// ENGINE PRINCIPAL EN RUST
// ============================================================

#[pyclass]
pub struct RustSimulationEngine {
    agents: Vec<Agent>,
    price: f64,
    rng: SmallRng,
    generation_length: i32,
    resource_name: String,
}

#[pymethods]
impl RustSimulationEngine {
    #[new]
    pub fn new(
        agents_data: Vec<HashMap<String, Py<PyAny>>>,
        initial_price: f64,
        seed: u64,
        generation_length: i32,
        resource_name: String,
        py: Python,
    ) -> PyResult<Self> {
        let mut agents = Vec::with_capacity(agents_data.len());
        for data in agents_data {
            let agent_id: i32 = data.get("agent_id").unwrap().extract(py)?;
            let species_str: String = data.get("species").unwrap().extract(py)?;
            let balance: f64 = data.get("balance").unwrap().extract(py)?;
            let inventory: i32 = data.get("inventory").unwrap().extract(py)?;
            let energy: f64 = data.get("energy").unwrap().extract(py)?;
            let buy_threshold: f64 = data.get("buy_threshold").unwrap().extract(py)?;
            let sell_threshold: f64 = data.get("sell_threshold").unwrap().extract(py)?;
            let production_rate: i32 = data.get("production_rate").unwrap().extract(py)?;
            let risk_tolerance: f64 = data.get("risk_tolerance").unwrap().extract(py)?;
            let momentum_bias: f64 = data.get("momentum_bias").unwrap().extract(py)?;
            let reproduction_drive: f64 = data.get("reproduction_drive").unwrap().extract(py)?;

            agents.push(Agent {
                agent_id,
                species: Species::from(species_str.as_str()),
                balance,
                inventory,
                energy,
                buy_threshold,
                sell_threshold,
                production_rate,
                risk_tolerance,
                momentum_bias,
                reproduction_drive,
                alive: true,
                generation: 0,
            });
        }

        Ok(RustSimulationEngine {
            agents,
            price: initial_price,
            rng: SmallRng::seed_from_u64(seed),
            generation_length,
            resource_name,
        })
    }

    pub fn run_tick(&mut self, tick: i32, shock: f64) -> PyResult<TickResult> {
        // 1. Evolución y producción
        for agent in self.agents.iter_mut() {
            if agent.alive {
                agent.evolve(shock);
                agent.produce(shock);
            }
        }

        // 2. Recolectar agentes vivos
        let alive_count = self.agents.iter().filter(|a| a.alive).count();
        let trend = 0.0;

        // 3. Decisiones
        let mut buyers = Vec::new();
        let mut sellers = Vec::new();

        for agent in self.agents.iter() {
            if !agent.alive {
                continue;
            }
            let decision = agent.decide(self.price, trend);
            match decision {
                Decision::Buy | Decision::Both => buyers.push(agent.agent_id),
                _ => {}
            }
            match decision {
                Decision::Sell | Decision::Both => sellers.push(agent.agent_id),
                _ => {}
            }
        }

        // 4. MATCHING con transacciones
        let mut tx_count = 0;
        let mut tx_list: Vec<(i32, i32, f64, i32)> = Vec::new();
        let mut buyer_pool: Vec<i32> = buyers.clone();
        let mut seller_pool: Vec<i32> = sellers.clone();

        buyer_pool.shuffle(&mut self.rng);
        seller_pool.shuffle(&mut self.rng);

        let agent_map: HashMap<i32, usize> = self.agents
            .iter()
            .enumerate()
            .map(|(idx, a)| (a.agent_id, idx))
            .collect();

        for &buyer_id in buyer_pool.iter() {
            if let Some(&seller_id) = seller_pool.first() {
                if buyer_id == seller_id {
                    continue;
                }

                if let (Some(&buyer_idx), Some(&seller_idx)) = (agent_map.get(&buyer_id), agent_map.get(&seller_id)) {
                    if buyer_idx == seller_idx {
                        continue;
                    }

                    if buyer_idx < seller_idx {
                        let (left, right) = self.agents.split_at_mut(seller_idx);
                        let buyer = &mut left[buyer_idx];
                        let seller = &mut right[0];

                        if buyer.alive && seller.alive && buyer.balance >= self.price && seller.inventory > 0 {
                            buyer.balance -= self.price;
                            buyer.inventory += 1;
                            seller.balance += self.price;
                            seller.inventory -= 1;
                            tx_count += 1;
                            tx_list.push((buyer_id, seller_id, self.price, 1));

                            if seller.inventory <= 0 {
                                seller_pool.retain(|&id| id != seller_id);
                            }
                        }
                    } else {
                        let (left, right) = self.agents.split_at_mut(buyer_idx);
                        let seller = &mut left[seller_idx];
                        let buyer = &mut right[0];

                        if buyer.alive && seller.alive && buyer.balance >= self.price && seller.inventory > 0 {
                            buyer.balance -= self.price;
                            buyer.inventory += 1;
                            seller.balance += self.price;
                            seller.inventory -= 1;
                            tx_count += 1;
                            tx_list.push((buyer_id, seller_id, self.price, 1));

                            if seller.inventory <= 0 {
                                seller_pool.retain(|&id| id != seller_id);
                            }
                        }
                    }
                }
            }
        }

        // 5. Actualizar precio (más volatilidad)
        let pressure = buyers.len() as f64 - sellers.len() as f64;
        let swing = 0.08 * pressure / (alive_count as f64).max(1.0);
        self.price = (self.price * (1.0 + swing) * shock).max(0.75).min(250.0);

        // 6. Limpiar muertos
        self.agents.retain(|a| a.alive);

        Ok(TickResult {
            tick,
            price: self.price,
            transactions: tx_count,
            buyers: buyers.len() as i32,
            sellers: sellers.len() as i32,
            survivors: alive_count as i32,
            tx_list: tx_list,
        })
    }

    pub fn get_price(&self) -> f64 {
        self.price
    }

    pub fn get_alive_count(&self) -> usize {
        self.agents.iter().filter(|a| a.alive).count()
    }

    pub fn get_agents(&self, py: Python) -> Vec<HashMap<String, Py<PyAny>>> {
        let mut result = Vec::new();
        for agent in &self.agents {
            let mut map = HashMap::new();
            map.insert("agent_id".to_string(), agent.agent_id.into_pyobject(py).unwrap().into());
            map.insert("species".to_string(), String::from(agent.species).into_pyobject(py).unwrap().into());
            map.insert("balance".to_string(), agent.balance.into_pyobject(py).unwrap().into());
            map.insert("inventory".to_string(), agent.inventory.into_pyobject(py).unwrap().into());
            map.insert("energy".to_string(), agent.energy.into_pyobject(py).unwrap().into());
            map.insert("buy_threshold".to_string(), agent.buy_threshold.into_pyobject(py).unwrap().into());
            map.insert("sell_threshold".to_string(), agent.sell_threshold.into_pyobject(py).unwrap().into());
            map.insert("production_rate".to_string(), agent.production_rate.into_pyobject(py).unwrap().into());
            map.insert("risk_tolerance".to_string(), agent.risk_tolerance.into_pyobject(py).unwrap().into());
            map.insert("momentum_bias".to_string(), agent.momentum_bias.into_pyobject(py).unwrap().into());
            map.insert("reproduction_drive".to_string(), agent.reproduction_drive.into_pyobject(py).unwrap().into());
            map.insert("alive".to_string(), agent.alive.into_py_any(py).unwrap());
            map.insert("generation".to_string(), agent.generation.into_pyobject(py).unwrap().into());
            result.push(map);
        }
        result
    }
}

// ============================================================
// MÓDULO PYTHON
// ============================================================

#[pymodule]
fn evolucionia_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustSimulationEngine>()?;
    m.add_class::<TickResult>()?;
    Ok(())
}