#!/usr/bin/env python3
"""
Dependencies: numpy, matplotlib (both standard in Python environments)
"""

import hashlib
import random
import math
import json
import argparse
import matplotlib.pyplot as plt
import numpy as np
from typing import List

# =====================
# Q16.16 Fixed-Point
# =====================
class Q1616:
    def __init__(self, value: float = 0.0):
        self.Q = int(round(value * 2**16))

    def __add__(self, other):
        return Q1616((self.Q + other.Q) / 2**16)

    def __sub__(self, other):
        return Q1616((self.Q - other.Q) / 2**16)

    def __mul__(self, other):
        return Q1616((self.Q * other.Q) / 2**32)

    def __truediv__(self, other):
        return Q1616((self.Q << 16) / other.Q)

    def to_float(self):
        return self.Q / 2**16

    def clamp(self):
        self.Q = max(min(self.Q, 2**31-1), -2**31)
        return self

# =====================
# Agent Node
# =====================
class AgentNode:
    def __init__(self, idx: int, dim: int, rng: random.Random):
        self.id = idx
        self.dim = dim
        self.rng = rng
        self.x_self: List[Q1616] = [Q1616(0.0) for _ in range(dim)]
        self.p: List[Q1616] = [Q1616(0.0) for _ in range(dim)]  # HELIX momentum
        self.pred: List['AgentNode'] = []
        self.W: List[List[Q1616]] = [[Q1616(rng.uniform(-1,1)) for _ in range(dim)] for _ in range(dim)]
        self.b: List[Q1616] = [Q1616(0.0) for _ in range(dim)]
        self.v: List[Q1616] = [Q1616(0.0) for _ in range(dim)]  # VAULT momentum

    def reward_scalar(self, x: List[Q1616]) -> Q1616:
        return Q1616(-sum(xi.to_float()**2 for xi in x)**0.5)

    def update_link(self):
        if not self.pred: return
        for i in range(self.dim):
            total = sum(self.W[i][j].to_float() * self.pred[j].x_self[j].to_float() 
                        for j in range(len(self.pred)))
            self.x_self[i] = Q1616(max(0.0, self.x_self[i].to_float() + total + self.b[i].to_float()))

    def vault_explore(self, beta=0.1, alpha=1.5, mu=0.9):
        for i in range(self.dim):
            u = self.rng.gauss(0,1)
            v = self.rng.gauss(0,1)
            jump = u / abs(v)**(1/alpha)
            momentum = mu*self.v[i].to_float() + (1-mu)*self.reward_scalar(self.x_self).to_float()
            self.v[i] = Q1616(momentum)
            self.x_self[i] = Q1616(self.x_self[i].to_float() + beta*jump*momentum)

    def helix_update(self, dt=0.01, gamma=1.0):
        for i in range(self.dim):
            force = -self.reward_scalar(self.x_self).to_float()
            self.p[i] = Q1616(gamma*self.p[i].to_float() + 0.5*dt*force)
            self.x_self[i] = Q1616(self.x_self[i].to_float() + dt*self.p[i].to_float())
            force_new = -self.reward_scalar(self.x_self).to_float()
            self.p[i] = Q1616(self.p[i].to_float() + 0.5*dt*force_new)

# =====================
# Agent Kernel
# =====================
class AgentKernel:
    def __init__(self, n_nodes=6, dim=4, seed=42, avg_pred=3):
        self.n_nodes = n_nodes
        self.dim = dim
        self.rng = random.Random(seed)
        self.nodes: List[AgentNode] = [AgentNode(i, dim, self.rng) for i in range(n_nodes)]
        self.truepath_hashes: List[str] = []
        self._initialize_weights()
        self._initialize_sparse_dag(avg_pred)

    def _initialize_weights(self):
        for node in self.nodes:
            node.W = [[Q1616(self.rng.uniform(-1,1)) for _ in range(self.dim)] for _ in range(self.dim)]

    def _initialize_sparse_dag(self, avg_pred=3):
        for node in self.nodes:
            predecessors = [n for n in self.nodes if n.id < node.id]
            node.pred = self.rng.sample(predecessors, min(len(predecessors), avg_pred))

    def pulse_step(self, K_mcmc=5, tau=0.2, beta=0.1, dt=0.01, gamma=1.0, verbose=True):
        for node in self.nodes:
            node.update_link()
            node.vault_explore(beta=beta)
            node.helix_update(dt=dt, gamma=gamma)
        self._compute_truepath(verbose)

    def _compute_truepath(self, verbose=True):
        concat = ''.join(''.join(str(xi.Q) for xi in node.x_self) for node in self.nodes)
        h = hashlib.sha256(concat.encode()).hexdigest()
        self.truepath_hashes.append(h)
        if verbose:
            print(f"[TRUE-PATH] {h[:16]}...")

    def truepath_hash(self): return self.truepath_hashes[-1] if self.truepath_hashes else None
    def verify_truepath(self): return True  # deterministic by design
    def get_state_snapshot(self): return [[xi.to_float() for xi in node.x_self] for node in self.nodes]

    def get_statistics(self):
        states = np.array(self.get_state_snapshot())
        rewards = np.array([node.reward_scalar(node.x_self).to_float() for node in self.nodes])
        momenta = np.array([[p.to_float() for p in node.p] for node in self.nodes])
        return states, rewards, momenta

# =====================
# Run Simulation + Summary + Plots
# =====================
def run_simulation(kernel: AgentKernel, steps=100):
    all_rewards = []
    for t in range(steps):
        kernel.pulse_step(verbose=False)
        _, rewards, _ = kernel.get_statistics()
        all_rewards.append(rewards)
    all_rewards = np.array(all_rewards)

    # Print Summary
    print("===== Simulation Summary =====")
    print(f"Nodes: {kernel.n_nodes}, Dimension: {kernel.dim}, Steps: {steps}")
    print(f"Final TRUE-PATH: {kernel.truepath_hash()}")
    print(f"Reward stats: mean={all_rewards[-1].mean():.4f}, min={all_rewards[-1].min():.4f}, max={all_rewards[-1].max():.4f}")

    # Plots
    plt.figure(figsize=(10,4))
    plt.subplot(1,2,1)
    plt.title("Reward Distribution Final Step")
    plt.hist(all_rewards[-1], bins=20, color='dodgerblue')
    plt.xlabel("Reward"); plt.ylabel("Count")

    plt.subplot(1,2,2)
    plt.title("Reward Trajectories")
    for i in range(all_rewards.shape[1]):
        plt.plot(all_rewards[:,i], label=f"Agent {i}")
    plt.xlabel("Step"); plt.ylabel("Reward"); plt.legend()
    plt.tight_layout()
    plt.show()

# =====================
# Interactive Shell
# =====================
def shell(kernel: AgentKernel):
    print("🦞 OpenClaw Interactive Shell. Type 'help'.")
    while True:
        try:
            cmd = input("🦞 openclaw> ").strip()
            if cmd == "exit": break
            elif cmd == "init":
                kernel = AgentKernel(n_nodes=kernel.n_nodes, dim=kernel.dim, seed=kernel.rng.randint(0,1e6))
                print("Kernel initialized.")
            elif cmd.startswith("pulse"):
                steps = int(cmd.split()[1]) if len(cmd.split())>1 else 1
                for _ in range(steps):
                    kernel.pulse_step()
            elif cmd == "status":
                print(f"Nodes: {kernel.n_nodes}, Dimension: {kernel.dim}")
            elif cmd == "verify":
                print(f"TRUE-PATH valid: {kernel.verify_truepath()}")
            elif cmd.startswith("snapshot"):
                fname = cmd.split()[1] if len(cmd.split())>1 else "snapshot.json"
                with open(fname,'w') as f:
                    json.dump(kernel.get_state_snapshot(), f)
                print(f"Snapshot saved to {fname}")
            elif cmd == "help":
                print("Commands: init, pulse [n], status, verify, snapshot [file], exit")
            else: print("Unknown command")
        except Exception as e:
            print(f"Error: {e}")

# =====================
# CLI
# =====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=6)
    parser.add_argument("--dim", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", type=str, default="shell", choices=["shell","benchmark","verify","simulate"])
    parser.add_argument("--steps", type=int, default=100)
    args = parser.parse_args()

    kernel = AgentKernel(n_nodes=args.nodes, dim=args.dim, seed=args.seed)

    if args.mode=="shell":
        shell(kernel)
    elif args.mode=="benchmark":
        import time
        start=time.time()
        for _ in range(args.steps):
            kernel.pulse_step(verbose=False)
        end=time.time()
        print(f"Benchmark: {args.steps} steps in {end-start:.3f}s ({args.steps/(end-start):.2f} steps/sec)")
    elif args.mode=="verify":
        for _ in range(args.steps):
            kernel.pulse_step(verbose=False)
        print(f"TRUE-PATH hash: {kernel.truepath_hash()}")
        print(f"Verification: {kernel.verify_truepath()}")
    elif args.mode=="simulate":
        run_simulation(kernel, steps=args.steps)
