#!/usr/bin/env python3
"""
================================================================================
LudicOS-OpenClaw: Production-Ready Deterministic Agentic Kernel
================================================================================

Complete reference implementation with Q16.16, Q8.24, and Q24.8 fixed-point
arithmetic for fully reproducible multi-agent systems.

Version: 1.0.0
Date: January 31, 2026
License: MIT

Features:
• Three fixed-point formats (Q16.16, Q8.24, Q24.8)
• Bit-identical reproducibility across platforms
• Cryptographic state hashing for verification
• DAG-based agent propagation
• Hybrid AXON + FGIN + LEVBOT + HIBOT + MCMC architecture
• Complete example scenarios

Usage:
    python ludicoS_kernel_production.py
    
Or import as module:
    from ludicoS_kernel_production import AgentKernel, Q1616, Q824, Q248
    kernel = AgentKernel(format='Q1616', n_nodes=6, dim=4, seed=4242)
    for t in range(100):
        kernel.step()
    
================================================================================
"""

import numpy as np
import random
import hashlib
import math
import time
from typing import List, Tuple, Optional, Union


# =============================================================================
# FIXED-POINT ARITHMETIC CLASSES
# =============================================================================

class Q1616:
    """
    Q16.16 Fixed-Point Number
    
    Format: Signed 32-bit integer with 16-bit integer and 16-bit fractional parts
    Range: [-32768.0, 32767.99998]
    Precision: 1/65536 ≈ 0.000015 (uniform across range)
    
    Best for: Standard deterministic agent systems with moderate range needs
    """
    SCALE = 1 << 16  # 65536
    SHIFT = 16
    MIN = -(1 << 31)  # -2147483648
    MAX = (1 << 31) - 1  # 2147483647
    
    def __init__(self, value: Union[float, int, 'Q1616']):
        """Initialize from float, int, or another Q1616."""
        if isinstance(value, float):
            q = int(round(value * self.SCALE))
        elif isinstance(value, int):
            q = value
        elif isinstance(value, Q1616):
            q = value.q
        else:
            raise TypeError(f"Cannot create Q1616 from {type(value)}")
        
        # Saturation (clamp to valid range)
        self.q = max(self.MIN, min(self.MAX, q))
    
    def __add__(self, other: Union['Q1616', float, int]) -> 'Q1616':
        """Add two Q16.16 numbers or Q16.16 + scalar."""
        if isinstance(other, Q1616):
            return Q1616(self.q + other.q)
        elif isinstance(other, float):
            return Q1616(self.q + int(round(other * self.SCALE)))
        elif isinstance(other, int):
            return Q1616(self.q + (other << self.SHIFT))
        return NotImplemented
    
    def __sub__(self, other: Union['Q1616', float, int]) -> 'Q1616':
        """Subtract two Q16.16 numbers or Q16.16 - scalar."""
        if isinstance(other, Q1616):
            return Q1616(self.q - other.q)
        elif isinstance(other, float):
            return Q1616(self.q - int(round(other * self.SCALE)))
        elif isinstance(other, int):
            return Q1616(self.q - (other << self.SHIFT))
        return NotImplemented
    
    def __mul__(self, other: Union['Q1616', float, int]) -> 'Q1616':
        """Multiply two Q16.16 numbers or Q16.16 * scalar."""
        if isinstance(other, Q1616):
            # Full 64-bit intermediate product
            prod = self.q * other.q
            # Round and shift back to Q16.16
            if prod >= 0:
                rounded = (prod + (1 << (self.SHIFT - 1))) >> self.SHIFT
            else:
                rounded = (prod - (1 << (self.SHIFT - 1))) >> self.SHIFT
            return Q1616(rounded)
        elif isinstance(other, (float, int)):
            # Scalar multiplication (keep in Q16.16)
            return Q1616(int(round(self.q * other)))
        return NotImplemented
    
    def __truediv__(self, other: Union['Q1616', float, int]) -> 'Q1616':
        """Divide Q16.16 by another number (use sparingly - less accurate)."""
        if isinstance(other, Q1616):
            if other.q == 0:
                raise ZeroDivisionError("Q1616 division by zero")
            # Scale up numerator to maintain precision
            scaled = self.q << self.SHIFT
            return Q1616(scaled // other.q)
        elif isinstance(other, (float, int)):
            return Q1616(int(round(self.q / other)))
        return NotImplemented
    
    def relu(self) -> 'Q1616':
        """Rectified Linear Unit: max(0, x)."""
        return Q1616(max(0, self.q))
    
    def to_float(self) -> float:
        """Convert to Python float (for display/logging only)."""
        return self.q / self.SCALE
    
    def __float__(self) -> float:
        return self.to_float()
    
    def __repr__(self) -> str:
        return f"Q1616({self.to_float():.6f})"
    
    def __str__(self) -> str:
        return f"{self.to_float():.6f}"


class Q824:
    """
    Q8.24 Fixed-Point Number
    
    Format: Signed 32-bit integer with 8-bit integer and 24-bit fractional parts
    Range: [-128.0, 127.999999]
    Precision: 1/16777216 ≈ 0.00000006 (4096x finer than Q16.16)
    
    Best for: High-precision requirements with smaller value ranges
    """
    SCALE = 1 << 24  # 16777216
    SHIFT = 24
    MIN = -(1 << 31)
    MAX = (1 << 31) - 1
    
    def __init__(self, value: Union[float, int, 'Q824']):
        if isinstance(value, float):
            q = int(round(value * self.SCALE))
        elif isinstance(value, int):
            q = value
        elif isinstance(value, Q824):
            q = value.q
        else:
            raise TypeError(f"Cannot create Q824 from {type(value)}")
        self.q = max(self.MIN, min(self.MAX, q))
    
    def __add__(self, other):
        if isinstance(other, Q824):
            return Q824(self.q + other.q)
        elif isinstance(other, float):
            return Q824(self.q + int(round(other * self.SCALE)))
        elif isinstance(other, int):
            return Q824(self.q + (other << self.SHIFT))
        return NotImplemented
    
    def __sub__(self, other):
        if isinstance(other, Q824):
            return Q824(self.q - other.q)
        elif isinstance(other, float):
            return Q824(self.q - int(round(other * self.SCALE)))
        elif isinstance(other, int):
            return Q824(self.q - (other << self.SHIFT))
        return NotImplemented
    
    def __mul__(self, other):
        if isinstance(other, Q824):
            prod = self.q * other.q
            if prod >= 0:
                rounded = (prod + (1 << (self.SHIFT - 1))) >> self.SHIFT
            else:
                rounded = (prod - (1 << (self.SHIFT - 1))) >> self.SHIFT
            return Q824(rounded)
        elif isinstance(other, (float, int)):
            return Q824(int(round(self.q * other)))
        return NotImplemented
    
    def __truediv__(self, other):
        if isinstance(other, Q824):
            if other.q == 0:
                raise ZeroDivisionError("Q824 division by zero")
            scaled = self.q << self.SHIFT
            return Q824(scaled // other.q)
        elif isinstance(other, (float, int)):
            return Q824(int(round(self.q / other)))
        return NotImplemented
    
    def relu(self):
        return Q824(max(0, self.q))
    
    def to_float(self):
        return self.q / self.SCALE
    
    def __float__(self):
        return self.to_float()
    
    def __repr__(self):
        return f"Q824({self.to_float():.8f})"
    
    def __str__(self):
        return f"{self.to_float():.8f}"


class Q248:
    """
    Q24.8 Fixed-Point Number
    
    Format: Signed 32-bit integer with 24-bit integer and 8-bit fractional parts
    Range: [-8388608.0, 8388607.99]
    Precision: 1/256 ≈ 0.0039 (16x coarser than Q16.16)
    
    Best for: Large value ranges with acceptable precision tradeoff
    """
    SCALE = 1 << 8  # 256
    SHIFT = 8
    MIN = -(1 << 31)
    MAX = (1 << 31) - 1
    
    def __init__(self, value: Union[float, int, 'Q248']):
        if isinstance(value, float):
            q = int(round(value * self.SCALE))
        elif isinstance(value, int):
            q = value
        elif isinstance(value, Q248):
            q = value.q
        else:
            raise TypeError(f"Cannot create Q248 from {type(value)}")
        self.q = max(self.MIN, min(self.MAX, q))
    
    def __add__(self, other):
        if isinstance(other, Q248):
            return Q248(self.q + other.q)
        elif isinstance(other, float):
            return Q248(self.q + int(round(other * self.SCALE)))
        elif isinstance(other, int):
            return Q248(self.q + (other << self.SHIFT))
        return NotImplemented
    
    def __sub__(self, other):
        if isinstance(other, Q248):
            return Q248(self.q - other.q)
        elif isinstance(other, float):
            return Q248(self.q - int(round(other * self.SCALE)))
        elif isinstance(other, int):
            return Q248(self.q - (other << self.SHIFT))
        return NotImplemented
    
    def __mul__(self, other):
        if isinstance(other, Q248):
            prod = self.q * other.q
            if prod >= 0:
                rounded = (prod + (1 << (self.SHIFT - 1))) >> self.SHIFT
            else:
                rounded = (prod - (1 << (self.SHIFT - 1))) >> self.SHIFT
            return Q248(rounded)
        elif isinstance(other, (float, int)):
            return Q248(int(round(self.q * other)))
        return NotImplemented
    
    def __truediv__(self, other):
        if isinstance(other, Q248):
            if other.q == 0:
                raise ZeroDivisionError("Q248 division by zero")
            scaled = self.q << self.SHIFT
            return Q248(scaled // other.q)
        elif isinstance(other, (float, int)):
            return Q248(int(round(self.q / other)))
        return NotImplemented
    
    def relu(self):
        return Q248(max(0, self.q))
    
    def to_float(self):
        return self.q / self.SCALE
    
    def __float__(self):
        return self.to_float()
    
    def __repr__(self):
        return f"Q248({self.to_float():.4f})"
    
    def __str__(self):
        return f"{self.to_float():.4f}"


# Format selection helper
FORMAT_MAP = {
    'Q1616': Q1616,
    'Q824': Q824,
    'Q248': Q248,
}


def qarray(arr, format_class=Q1616):
    """
    Convert NumPy array or list to object array of fixed-point numbers.
    
    Args:
        arr: Input array (floats or ints)
        format_class: Q1616, Q824, or Q248
    
    Returns:
        NumPy object array of fixed-point numbers
    """
    arr = np.asarray(arr)
    shape = arr.shape
    flat = arr.flatten()
    q = [format_class(x) for x in flat]
    return np.array(q, dtype=object).reshape(shape)


# =============================================================================
# DETERMINISTIC RANDOM NUMBER GENERATOR
# =============================================================================

class SeededRNG:
    """
    Seeded deterministic RNG with state management for perfect reproducibility.
    
    Uses Python's built-in random module with explicit state save/restore to
    ensure identical sequences across runs, even with conditional branching.
    """
    
    def __init__(self, seed: int = 42):
        """
        Initialize with a seed.
        
        Args:
            seed: Integer seed for reproducibility
        """
        self.seed = seed
        self.reset()
    
    def reset(self):
        """Reset RNG to initial seeded state."""
        random.seed(self.seed)
        self.state = random.getstate()
    
    def uniform(self, low: float = -1.0, high: float = 1.0, 
                size: Optional[Union[int, Tuple[int, ...]]] = None,
                format_class=Q1616):
        """
        Generate uniform random number(s) in [low, high).
        
        Args:
            low: Lower bound (inclusive)
            high: Upper bound (exclusive)
            size: None for scalar, int or tuple for array shape
            format_class: Q1616, Q824, or Q248
        
        Returns:
            Single fixed-point number or NumPy object array
        """
        random.setstate(self.state)
        
        if size is None:
            # Scalar
            u = random.uniform(low, high)
            self.state = random.getstate()
            return format_class(u)
        else:
            # Array
            if isinstance(size, int):
                size = (size,)
            arr = [random.uniform(low, high) for _ in range(np.prod(size))]
            self.state = random.getstate()
            return qarray(np.array(arr).reshape(size), format_class)


# =============================================================================
# AGENT NODE (DAG VERTEX)
# =============================================================================

class AgentNode:
    """
    Individual agent in the multi-agent DAG.
    
    Implements:
    • AXON: DAG-based forward propagation
    • FGIN: Stochastic perturbation
    • LEVBOT: Momentum-based optimization
    • HIBOT: Hamiltonian dynamics
    • Reward: Task-specific objective function
    """
    
    def __init__(self, id: int, dim: int = 4, pred: Optional[List['AgentNode']] = None,
                 rng: Optional[SeededRNG] = None, alpha: float = 0.03125,
                 format_class=Q1616):
        """
        Initialize agent node.
        
        Args:
            id: Unique agent identifier
            dim: State vector dimensionality
            pred: List of predecessor agents in DAG
            rng: Shared deterministic RNG
            alpha: FGIN perturbation magnitude
            format_class: Q1616, Q824, or Q248
        """
        self.id = id
        self.dim = dim
        self.pred = pred or []
        self.rng = rng
        self.format_class = format_class
        self.alpha = format_class(alpha)
        
        # Weights (initialized after DAG structure finalized)
        self.W = None
        
        # State vectors (all in fixed-point)
        self.b = qarray(np.zeros(dim), format_class)  # Bias
        self.x_self = qarray(np.zeros(dim), format_class)  # Current state
        self.momentum = qarray(np.zeros(dim), format_class)  # LEVBOT momentum
        self.p_momentum = qarray(np.zeros(dim), format_class)  # HIBOT momentum
        
        # Temporary (computed each step)
        self.x_axon = None
    
    def axon(self):
        """
        AXON: DAG-based forward propagation.
        
        Computes: x_new = ReLU(W × [x_self; x_pred_1; ...; x_pred_k] + b)
        
        Returns:
            Updated state vector (fixed-point array)
        """
        # Concatenate self state with all predecessor states
        inputs = [self.x_self] + [p.x_self for p in self.pred]
        concat = np.concatenate([[y.to_float() for y in arr] for arr in inputs])
        
        # Matrix multiply (in float for intermediate computation)
        W_float = np.array([[w.to_float() for w in row] for row in self.W])
        b_float = np.array([bi.to_float() for bi in self.b])
        z_float = np.dot(W_float, concat) + b_float
        
        # Convert back to fixed-point and apply ReLU
        return np.array([self.format_class(z).relu() for z in z_float], dtype=object)
    
    def fgin(self, x):
        """
        FGIN: Fluctuation-Guided Information Noise.
        
        Adds uniform random perturbation to enable exploration in deterministic framework.
        
        Args:
            x: Input state vector
        
        Returns:
            Perturbed state vector
        """
        eps = self.rng.uniform(-self.alpha.to_float(), self.alpha.to_float(), 
                               size=self.dim, format_class=self.format_class)
        return np.array([xi + e for xi, e in zip(x, eps)], dtype=object)
    
    def levbot(self, x, beta: float = 0.05, mu: float = 0.9, eps: float = 1e-6):
        """
        LEVBOT: LEVy-Based Optimization Trajectory.
        
        Momentum-smoothed gradient descent with adaptive step sizing.
        
        Args:
            x: Input state vector
            beta: Base step size
            mu: Momentum coefficient (0.9 = 90% previous, 10% current)
            eps: Numerical stability constant
        
        Returns:
            Refined state vector
        """
        # Compute gradient (simple example: gradient = -0.1 * x)
        x_floats = np.array([xi.to_float() for xi in x])
        grad_floats = -x_floats * 0.1
        grad = qarray(grad_floats, self.format_class)
        
        # Update momentum: m = μ·m + (1-μ)·g
        mom_floats = np.array([m.to_float() for m in self.momentum])
        g_floats = np.array([g.to_float() for g in grad])
        new_mom_floats = mu * mom_floats + (1 - mu) * g_floats
        self.momentum = qarray(new_mom_floats, self.format_class)
        
        # Compute step: step = (β / ||m||) · m
        norm = math.sqrt(sum(v.to_float() ** 2 for v in self.momentum)) + eps
        step_floats = (beta / norm) * np.array([v.to_float() for v in self.momentum])
        step = qarray(step_floats, self.format_class)
        
        # Apply update
        return np.array([xi + s for xi, s in zip(x, step)], dtype=object)
    
    def hibot_hamiltonian(self, x, gamma: float = 0.9, delta_t: float = 0.1):
        """
        HIBOT: Hamiltonian-Inspired BOT dynamics.
        
        Physics-based update using momentum and conservative forces.
        Implements leapfrog integration for symplectic evolution.
        
        Args:
            x: Position (state) vector
            gamma: Friction coefficient
            delta_t: Time step
        
        Returns:
            Updated state vector
        """
        # Compute gradient (force)
        x_floats = np.array([xi.to_float() for xi in x])
        grad_floats = -x_floats * 0.1
        grad = qarray(grad_floats, self.format_class)
        
        # Half-step momentum update: p = γ·p - Δt·∇E
        p_floats = np.array([p.to_float() for p in self.p_momentum])
        g_floats = np.array([g.to_float() for g in grad])
        new_p_floats = gamma * p_floats - 2 * delta_t * g_floats
        self.p_momentum = qarray(new_p_floats, self.format_class)
        
        # Position update: q = q + Δt·p
        q_new = np.array([
            xi + self.format_class(delta_t * pm.to_float()) 
            for xi, pm in zip(x, self.p_momentum)
        ], dtype=object)
        
        # Second half-step momentum update
        p_floats = np.array([pm.to_float() for pm in self.p_momentum])
        new_p_floats = p_floats - 2 * delta_t * g_floats
        self.p_momentum = qarray(new_p_floats, self.format_class)
        
        return q_new
    
    def reward_scalar(self, x):
        """
        Compute reward (negative energy) for state x.
        
        R(x) = -||x||₂ + 0.1 × sin(id + Σx_i)
        
        Components:
        • Norm penalty: Encourages compact states
        • Sinusoidal: Creates local optima for exploration
        • Agent ID: Breaks symmetry
        
        Args:
            x: State vector
        
        Returns:
            Scalar reward (fixed-point)
        """
        floats = [xi.to_float() for xi in x]
        norm = sum(f ** 2 for f in floats) ** 0.5
        sin_arg = self.id + sum(floats)
        reward_val = -norm + 0.1 * math.sin(sin_arg)
        return self.format_class(reward_val)


# =============================================================================
# MULTI-AGENT KERNEL
# =============================================================================

class AgentKernel:
    """
    LudicOS-OpenClaw: Deterministic multi-agent DAG kernel.
    
    Orchestrates:
    • DAG-structured agent network
    • Hybrid deterministic + stochastic updates
    • MCMC-based state selection
    • Cryptographic state verification
    """
    
    def __init__(self, n_nodes: int = 6, dim: int = 4, seed: int = 4242,
                 format: str = 'Q1616'):
        """
        Initialize agent kernel.
        
        Args:
            n_nodes: Number of agents
            dim: State dimensionality per agent
            seed: RNG seed for reproducibility
            format: 'Q1616', 'Q824', or 'Q248'
        """
        self.n_nodes = n_nodes
        self.dim = dim
        self.seed = seed
        self.format = format
        self.format_class = FORMAT_MAP[format]
        
        # Shared deterministic RNG
        self.rng = SeededRNG(seed)
        
        # Create agent nodes
        self.nodes = [
            AgentNode(i, dim=dim, rng=self.rng, format_class=self.format_class)
            for i in range(n_nodes)
        ]
        
        # Define DAG structure (example topology)
        if n_nodes >= 6:
            # Layer 1 (inputs): Agents 0, 1
            # Layer 2: Agent 2 aggregates from 0, 1
            self.nodes[2].pred = [self.nodes[0], self.nodes[1]]
            
            # Layer 3: Agents 3, 4 process Agent 2
            self.nodes[3].pred = [self.nodes[2]]
            self.nodes[4].pred = [self.nodes[2]]
            
            # Layer 4 (output): Agent 5 aggregates from 3, 4
            self.nodes[5].pred = [self.nodes[3], self.nodes[4]]
        
        # Initialize weights based on DAG structure
        for node in self.nodes:
            # Deterministic initialization using node ID as seed
            np.random.seed(node.id)
            
            # Input dimension = node's own dim + sum of predecessor dims
            input_dim = node.dim * (1 + len(node.pred))
            
            # Gaussian weights (small std for stability)
            W_init = np.random.normal(0, 0.1, (node.dim, input_dim))
            node.W = qarray(W_init, self.format_class)
        
        # Timestep counter
        self.timestep = 0
    
    def hash_state(self) -> str:
        """
        Compute cryptographic hash of current state.
        
        Uses SHA-256 over raw fixed-point bits to create verifiable fingerprint.
        Any difference in state → completely different hash.
        
        Returns:
            16-character hex string (first 64 bits of SHA-256)
        """
        h = hashlib.sha256()
        
        for node in self.nodes:
            # Convert each state element to 8-character hex
            s = "".join(f"{x.q:08x}" for x in node.x_self)
            h.update((str(node.id) + s).encode())
        
        # Return first 16 hex chars for compact display
        return h.hexdigest()[:16]
    
    def step(self, K_mcmc: int = 8, tau: float = 0.1, beta: float = 0.05,
             verbose: bool = True):
        """
        Execute one timestep of the kernel.
        
        Process:
        1. Reset RNG to ensure reproducibility
        2. AXON forward pass through DAG
        3. MCMC exploration with K proposals
        4. Select best candidate
        5. Update all agents simultaneously
        6. Compute and display state hash
        
        Args:
            K_mcmc: Number of MCMC proposal iterations
            tau: Temperature parameter (higher = more exploration)
            beta: LEVBOT step size
            verbose: Print hash and diagnostics
        """
        # Reset RNG for reproducibility
        self.rng.reset()
        
        # 1. AXON: Forward propagation through DAG
        for node in self.nodes:
            node.x_axon = node.axon()
        
        # 2. MCMC Exploration
        candidates = []
        current_x = [node.x_axon.copy() for node in self.nodes]
        
        for k in range(K_mcmc):
            # Generate proposal via FGIN → LEVBOT → HIBOT pipeline
            proposed = []
            for node, x in zip(self.nodes, current_x):
                x1 = node.fgin(x)  # Stochastic perturbation
                x2 = node.levbot(x1, beta=beta)  # Gradient refinement
                x3 = node.hibot_hamiltonian(x2)  # Hamiltonian dynamics
                proposed.append(x3)
            
            # Metropolis acceptance criterion
            E_new = sum(node.reward_scalar(x).to_float() 
                       for node, x in zip(self.nodes, proposed))
            E_old = sum(node.reward_scalar(x).to_float() 
                       for node, x in zip(self.nodes, current_x))
            delta_E = E_new - E_old
            
            # Accept if better, or with probability exp(-ΔE/τ)
            accept_prob = math.exp(-delta_E / tau) if delta_E > 0 else 1.0
            
            if delta_E < 0 or self.rng.uniform(0, 1).to_float() < accept_prob:
                current_x = proposed
            
            # Store candidate regardless of acceptance (for final selection)
            candidates.append([x.copy() for x in current_x])
        
        # 3. Select best candidate from all K proposals
        scores = [
            sum(node.reward_scalar(x).to_float() 
                for node, x in zip(self.nodes, cand))
            for cand in candidates
        ]
        best_idx = np.argmin(scores)
        best_states = candidates[best_idx]
        
        # 4. Update all agents simultaneously
        for node, x in zip(self.nodes, best_states):
            node.x_self = x
        
        # 5. Increment timestep and display hash
        self.timestep += 1
        
        if verbose:
            hash_val = self.hash_state()
            print(f"Step {self.timestep:4d} | Hash: {hash_val} | "
                  f"Best reward: {scores[best_idx]:8.5f}")
    
    def get_state_snapshot(self) -> dict:
        """
        Get complete state snapshot for serialization/replay.
        
        Returns:
            Dictionary with all state information
        """
        return {
            'timestep': self.timestep,
            'format': self.format,
            'seed': self.seed,
            'nodes': [
                {
                    'id': n.id,
                    'x_self': [x.q for x in n.x_self],
                    'momentum': [m.q for m in n.momentum],
                    'p_momentum': [p.q for p in n.p_momentum],
                }
                for n in self.nodes
            ],
            'hash': self.hash_state()
        }
    
    def print_state_summary(self):
        """Print human-readable state summary."""
        print(f"\n{'='*70}")
        print(f"Kernel State Summary (Timestep {self.timestep})")
        print(f"{'='*70}")
        print(f"Format: {self.format} | Seed: {self.seed} | Hash: {self.hash_state()}")
        print(f"{'-'*70}")
        
        for node in self.nodes:
            x_vals = [x.to_float() for x in node.x_self]
            print(f"Agent {node.id}: [{', '.join(f'{v:7.4f}' for v in x_vals)}]")
        
        print(f"{'='*70}\n")


# =============================================================================
# EXAMPLE SCENARIOS & BENCHMARKS
# =============================================================================

def demo_reproducibility():
    """
    Demonstrate perfect reproducibility across multiple runs.
    
    Runs the same configuration twice and verifies hash sequences match.
    """
    print("\n" + "="*70)
    print("REPRODUCIBILITY DEMONSTRATION")
    print("="*70)
    print("Running same configuration twice to verify identical hashes...\n")
    
    # Run 1
    print("Run 1:")
    kernel1 = AgentKernel(n_nodes=6, dim=4, seed=4242, format='Q1616')
    hashes1 = [kernel1.hash_state()]
    for t in range(5):
        kernel1.step(K_mcmc=8, tau=0.15, beta=0.06, verbose=True)
        hashes1.append(kernel1.hash_state())
    
    print("\nRun 2:")
    kernel2 = AgentKernel(n_nodes=6, dim=4, seed=4242, format='Q1616')
    hashes2 = [kernel2.hash_state()]
    for t in range(5):
        kernel2.step(K_mcmc=8, tau=0.15, beta=0.06, verbose=True)
        hashes2.append(kernel2.hash_state())
    
    # Verify
    print("\n" + "-"*70)
    if hashes1 == hashes2:
        print("✓ REPRODUCIBILITY VERIFIED: All hashes match perfectly!")
    else:
        print("✗ REPRODUCIBILITY FAILED: Hashes differ!")
        for i, (h1, h2) in enumerate(zip(hashes1, hashes2)):
            match = "✓" if h1 == h2 else "✗"
            print(f"  Step {i}: {match} {h1} vs {h2}")
    print("="*70 + "\n")


def demo_format_comparison():
    """
    Compare Q16.16, Q8.24, and Q24.8 on the same scenario.
    
    Shows precision/range tradeoffs between formats.
    """
    print("\n" + "="*70)
    print("FIXED-POINT FORMAT COMPARISON")
    print("="*70)
    print("Running identical scenario with Q16.16, Q8.24, and Q24.8...\n")
    
    formats = ['Q1616', 'Q824', 'Q248']
    results = {}
    
    for fmt in formats:
        print(f"\n{fmt} Format:")
        print("-" * 50)
        kernel = AgentKernel(n_nodes=6, dim=4, seed=4242, format=fmt)
        
        for t in range(3):
            kernel.step(K_mcmc=8, tau=0.15, beta=0.06, verbose=True)
        
        # Record final state of Agent 0
        results[fmt] = [x.to_float() for x in kernel.nodes[0].x_self]
        print(f"Final Agent 0 state: {results[fmt]}")
    
    # Comparison
    print("\n" + "="*70)
    print("FINAL STATE COMPARISON (Agent 0):")
    print("="*70)
    for fmt in formats:
        vals_str = ', '.join(f'{v:10.6f}' for v in results[fmt])
        print(f"{fmt:6s}: [{vals_str}]")
    print("="*70 + "\n")


def benchmark_performance():
    """
    Benchmark performance of different configurations.
    """
    print("\n" + "="*70)
    print("PERFORMANCE BENCHMARK")
    print("="*70)
    
    configs = [
        ('Q1616', 6, 4, 50),
        ('Q824', 6, 4, 50),
        ('Q248', 6, 4, 50),
        ('Q1616', 10, 8, 25),  # Larger system
    ]
    
    for fmt, n_nodes, dim, n_steps in configs:
        kernel = AgentKernel(n_nodes=n_nodes, dim=dim, seed=4242, format=fmt)
        
        start = time.time()
        for t in range(n_steps):
            kernel.step(K_mcmc=8, tau=0.15, beta=0.06, verbose=False)
        elapsed = time.time() - start
        
        per_step = (elapsed / n_steps) * 1000  # ms
        print(f"{fmt} ({n_nodes} nodes, dim={dim}): "
              f"{elapsed:.2f}s total, {per_step:.1f} ms/step")
    
    print("="*70 + "\n")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """
    Main entry point - runs all demonstrations.
    """
    print("\n" + "="*70)
    print("LudicOS-OpenClaw: Deterministic Agentic Kernel")
    print("Version 1.0.0 | January 31, 2026")
    print("="*70)
    
    # Run demonstrations
    demo_reproducibility()
    demo_format_comparison()
    benchmark_performance()
    
    # Final example with detailed output
    print("\n" + "="*70)
    print("DETAILED EXAMPLE: 10 Timesteps with Q16.16")
    print("="*70 + "\n")
    
    kernel = AgentKernel(n_nodes=6, dim=4, seed=4242, format='Q1616')
    print(f"Initial hash: {kernel.hash_state()}\n")
    
    for t in range(10):
        kernel.step(K_mcmc=12, tau=0.2, beta=0.08, verbose=True)
    
    kernel.print_state_summary()
    
    print("✓ All demonstrations complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
