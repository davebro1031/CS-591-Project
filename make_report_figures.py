"""Regenerate the figures and numbers used in the final report.

The model and solver are not re-implemented here. This script executes the code
cells of chicken.ipynb that sit above the "## Visualizations" heading, exactly
as they are in the notebook, and then derives the quantities reported in
Section 4 and the appendix of the final report:

  * value maps and equilibrium swerve probabilities (figures),
  * the terminal-state distribution reached under the equilibrium policy pair,
  * the closed-form check of the mixed equilibrium at last-decision states,
  * possible / sure reachability of a win and sure avoidance of a crash.

Usage (with the project environment from requirements.txt active):

    python make_report_figures.py             # figures + numbers
    python make_report_figures.py --variants  # also the payoff variants
    python make_report_figures.py --outdir some/folder

The notebook is read from the folder that contains this script. The figures are
written to its plots/ subfolder unless --outdir names another folder.
"""

import argparse
import contextlib
import io
import json
import os
import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "chicken.ipynb"
PLOTS = HERE / "plots"

SWERVE = "swerve"
ACTION_FROM_LABEL = {"swerve": SWERVE, "do nothing": 0, "speed up": 1, "slow down": -1}
# Notebook name -> report name. "s+" means only player 1 (the notebook's "+") swerves.
TERMINALS = ("s-", "s+", "s0", "crash")


# ----------------------------------------------------------------------------
# Run the notebook's own model and solver cells
# ----------------------------------------------------------------------------
def run_notebook(patches=()):
    """Execute the notebook cells above '## Visualizations'.

    `patches` is a list of (old, new) source replacements, used only for the
    payoff variants. Returns (namespace, captured stdout, error or None).
    """
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    namespace, log, error = {}, io.StringIO(), None
    for cell in cells:
        source = "".join(cell["source"])
        if cell["cell_type"] == "markdown":
            if source.lstrip().startswith("## Visualizations"):
                break
            continue
        for old, new in patches:
            source = source.replace(old, new)
        try:
            with contextlib.redirect_stdout(log):
                exec(source, namespace)
        except Exception as exc:  # the notebook's solver stops on a degenerate state
            error = f"{type(exc).__name__}: {exc}"
            break
    else:
        raise RuntimeError("No '## Visualizations' markdown cell found in the notebook.")
    return namespace, log.getvalue(), error


class Game:
    """Solved game, read from the notebook namespace."""

    def __init__(self, ns):
        self.ns = ns
        self.values = ns["values"]  # {player: {state: value}}
        self.policy = ns["strats_nice"]  # {player: {state: {label: prob}}}
        self.kernel = ns["kernel"]
        self.v_min, self.v_max = ns["v_min"], ns["v_max"]
        numeric = [s for s in self.values[1] if isinstance(s, tuple)]
        self.live = sorted(s for s in numeric if s[0] > 0)
        self.crash = {s for s in numeric if s[0] == 0}
        self.speeds = list(range(self.v_min, self.v_max + 1))
        self._outcomes = {}

    def actions(self, s, player):
        v = s[1] if player == 1 else s[2]
        acts = [SWERVE, 0]
        if v < self.v_max:
            acts.append(1)
        if v > self.v_min:
            acts.append(-1)
        return acts

    def successor(self, s, a1, a2):
        (nxt, prob), = self.kernel(s, a1, a2).items()  # the kernel is deterministic
        assert prob == 1
        return nxt

    def mixed(self, s, player):
        """Equilibrium policy at s as {action: probability}."""
        return {ACTION_FROM_LABEL[lab]: float(p) for lab, p in self.policy[player][s].items()}

    def swerve_prob(self, s, player):
        return self.mixed(s, player).get(SWERVE, 0.0)

    def last_decision(self, s):
        return s[0] <= s[1] + s[2]

    # ---- forward propagation of the equilibrium policy pair ----
    def outcome(self, s):
        """(distribution over TERMINALS, expected number of joint moves) from s."""
        if s in self._outcomes:
            return self._outcomes[s]
        dist, moves = dict.fromkeys(TERMINALS, 0.0), 1.0
        for a1, p1 in self.mixed(s, 1).items():
            for a2, p2 in self.mixed(s, -1).items():
                nxt, w = self.successor(s, a1, a2), p1 * p2
                if isinstance(nxt, str):
                    dist[nxt] += w
                elif nxt[0] == 0:
                    dist["crash"] += w
                else:
                    sub, sub_moves = self.outcome(nxt)
                    for k in dist:
                        dist[k] += w * sub[k]
                    moves += w * sub_moves
        self._outcomes[s] = (dist, moves)
        return self._outcomes[s]

    # ---- reachability on the transition structure alone ----
    def sure_reach(self, player, target):
        """States from which `player` reaches `target` against every opponent."""
        region, changed = set(target), True
        while changed:
            changed = False
            for s in self.live:
                if s in region:
                    continue
                mine, theirs = self.actions(s, player), self.actions(s, -player)
                for a in mine:
                    nexts = [
                        self.successor(s, a, b) if player == 1 else self.successor(s, b, a)
                        for b in theirs
                    ]
                    if all(n in region for n in nexts):
                        region.add(s)
                        changed = True
                        break
        return region - set(target)

    def possible_reach(self, target):
        """States from which some joint play reaches `target`."""
        region, changed = set(target), True
        while changed:
            changed = False
            for s in self.live:
                if s in region:
                    continue
                if any(
                    self.successor(s, a, b) in region
                    for a in self.actions(s, 1)
                    for b in self.actions(s, -1)
                ):
                    region.add(s)
                    changed = True
        return region - set(target)

    # ---- closed form of the mixed equilibrium at last-decision states ----
    def closed_form_error(self):
        """Largest gap between the solver output and the indifference formula."""
        worst = 0.0
        for s in filter(self.last_decision, self.live):
            support = {}
            for player in (1, -1):
                acts = [a for a in self.mixed(s, player) if a != SWERVE]
                assert len(acts) == 1 and self.swerve_prob(s, player) > 0, s
                support[player] = acts[0]

            def payoff(player, a1, a2):
                own = a1 if player == 1 else a2
                reward = 0.1 * own if own != SWERVE else 0.0
                return self.values[player][self.successor(s, a1, a2)] + reward

            g1, g2 = support[1], support[-1]
            # win, lose (swerve alone), both swerve, crash -- for each player
            w = {1: payoff(1, g1, SWERVE), -1: payoff(-1, SWERVE, g2)}
            l = {1: payoff(1, SWERVE, g2), -1: payoff(-1, g1, SWERVE)}
            b = {1: payoff(1, SWERVE, SWERVE), -1: payoff(-1, SWERVE, SWERVE)}
            c = {1: payoff(1, g1, g2), -1: payoff(-1, g1, g2)}
            for i in (1, -1):
                opp_swerve = (l[i] - c[i]) / ((l[i] - c[i]) + (w[i] - b[i]))
                value = opp_swerve * b[i] + (1 - opp_swerve) * l[i]
                worst = max(
                    worst,
                    abs(opp_swerve - self.swerve_prob(s, -i)),
                    abs(value - self.values[i][s]),
                )
        return worst


# ----------------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------------
def heatmap(ax, game, cell_value, cmap, vmin, vmax, title, fmt="{:.2f}", outline=()):
    grid = np.array([[cell_value(v1, v2) for v1 in game.speeds] for v2 in game.speeds])
    image = ax.imshow(grid, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax)
    for row, v2 in enumerate(game.speeds):
        for col, v1 in enumerate(game.speeds):
            r, g, b, _ = image.cmap(image.norm(grid[row, col]))
            dark = 0.299 * r + 0.587 * g + 0.114 * b < 0.5
            label = fmt.format(grid[row, col]).replace("-", "\N{MINUS SIGN}")
            ax.text(col, row, label, ha="center", va="center",
                    fontsize=8, color="white" if dark else "black")
            if (v1, v2) in outline:
                ax.add_patch(Rectangle((col - 0.46, row - 0.46), 0.92, 0.92,
                                       fill=False, edgecolor="black", linewidth=1.6))
    ax.set_xticks(range(len(game.speeds)), game.speeds)
    ax.set_yticks(range(len(game.speeds)), game.speeds)
    ax.set_xlabel(r"$v^{1}$")
    ax.set_ylabel(r"$v^{-1}$")
    ax.set_title(title, fontsize=9)
    return image


def figure_value_maps(game, outdir):
    d_far = max(s[0] for s in game.live)
    two_decision = {(s[1], s[2]) for s in game.live if s[0] == d_far and not game.last_decision(s)}
    fig, axes = plt.subplots(2, 2, figsize=(6.4, 5.3), constrained_layout=True)
    for row, (player, name) in enumerate([(1, r"$V^{1}$"), (-1, r"$V^{-1}$")]):
        vals = [game.values[player][s] for s in game.live]
        lo, hi = min(vals), max(vals)
        heatmap(axes[row, 0], game, lambda v1, v2: game.values[player][(1, v1, v2)],
                "RdYlGn", lo, hi, name + r", last-decision states ($d \leq v^{1}+v^{-1}$)")
        image = heatmap(axes[row, 1], game, lambda v1, v2: game.values[player][(d_far, v1, v2)],
                        "RdYlGn", lo, hi, name + rf", initial distance $d={d_far}$",
                        outline=two_decision)
        fig.colorbar(image, ax=axes[row, :], shrink=0.85, pad=0.02)
    path = outdir / "value_maps.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def figure_policy_maps(game, outdir):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.55), constrained_layout=True)
    for ax, player in zip(axes[:2], (1, -1)):
        image = heatmap(ax, game, lambda v1, v2: game.swerve_prob((1, v1, v2), player),
                        "Blues", 0.0, 1.0, rf"Pr[player ${player}$ swerves]")
    fig.colorbar(image, ax=axes[:2], shrink=0.85, pad=0.02)
    image = heatmap(axes[2], game, lambda v1, v2: game.outcome((1, v1, v2))[0]["crash"],
                    "Reds", 0.0, 0.25, "Pr[crash]")
    fig.colorbar(image, ax=axes[2], shrink=0.85, pad=0.04)
    path = outdir / "policy_maps.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


# ----------------------------------------------------------------------------
# Numbers quoted in the report
# ----------------------------------------------------------------------------
def report_numbers(game, log):
    live, last = game.live, [s for s in game.live if game.last_decision(s)]
    two = [s for s in live if not game.last_decision(s)]
    print("== Setup ==")
    print(f"non-terminal states: {len(live)}  crash states: {len(game.crash)}")
    print(f"last-decision states: {len(last)}  two-decision states: {len(two)}")
    print(f"solver log: degenerate={log.count('degenerate')} "
          f"unmatched={log.count('unmatched')} multiple-equilibria states={log.count('Multiple equilibria')}")

    print("\n== Equilibria per state (re-solving one state of each kind) ==")
    with contextlib.redirect_stdout(io.StringIO()):
        counts_last = Counter(
            (len(eqs), len(game.ns["get_mixed_eqs"](eqs)))
            for eqs in (game.ns["evaluate_state"]((1, v1, v2)) for v1 in game.speeds for v2 in game.speeds)
        )
        counts_two = Counter(len(game.ns["evaluate_state"](s)) for s in two)
    print("last-decision (number of equilibria, number mixed) -> states:", dict(counts_last))
    print("two-decision number of equilibria -> states:", dict(counts_two))
    print("two-decision policies:", Counter(
        (tuple(game.mixed(s, 1).items()), tuple(game.mixed(s, -1).items())) for s in two))
    print("support of the non-swerve action at last-decision states:", dict(Counter(
        ("at v_min" if (s[1] if p == 1 else s[2]) == game.v_min else "above v_min",
         next(a for a in game.mixed(s, p) if a != SWERVE))
        for s in last for p in (1, -1))))

    print("\n== Values and policies ==")
    for player in (1, -1):
        vals = [game.values[player][s] for s in live]
        sw = [game.swerve_prob(s, player) for s in last]
        print(f"player {player:+d}: V in [{min(vals):.4f}, {max(vals):.4f}]  "
              f"swerve prob (last-decision) in [{min(sw):.4f}, {max(sw):.4f}]")
    print(f"closed form vs solver, max abs error: {game.closed_form_error():.2e}")

    print("\n== Outcome distribution under the equilibrium pair ==")
    names = {"s-": "only -1 swerves (1 wins)", "s+": "only 1 swerves (-1 wins)",
             "s0": "both swerve", "crash": "crash"}
    for key in TERMINALS:
        probs = [game.outcome(s)[0][key] for s in live]
        print(f"{names[key]:>26}: [{min(probs):.4f}, {max(probs):.4f}]")
    print("joint moves until termination -> states:", dict(Counter(game.outcome(s)[1] for s in live)))
    d_far = max(s[0] for s in live)
    print(f"\n{'state':>10} {'1 wins':>7} {'-1 wins':>7} {'both':>7} {'crash':>7} {'moves':>5} {'V1':>8} {'V-1':>8}")
    for v1, v2 in [(3, 3), (4, 4), (5, 5), (6, 6), (3, 6), (6, 3)]:
        s = (d_far, v1, v2)
        dist, moves = game.outcome(s)
        print(f"{str(s):>10} {dist['s-']:7.3f} {dist['s+']:7.3f} {dist['s0']:7.3f} {dist['crash']:7.3f} "
              f"{moves:5.0f} {game.values[1][s]:8.3f} {game.values[-1][s]:8.3f}")

    print("\n== Reachability on the transition structure ==")
    print("possible win, player 1 / -1:", len(game.possible_reach({"s-"})), len(game.possible_reach({"s+"})))
    print("sure win, player 1 / -1:    ", len(game.sure_reach(1, {"s-"})), len(game.sure_reach(-1, {"s+"})))
    swerve_states = {"s+", "s-", "s0"}
    print("sure no crash, player 1 / -1:", len(game.sure_reach(1, swerve_states)),
          len(game.sure_reach(-1, swerve_states)))
    greedy = Counter(
        max(["s+", "s-", "s0"] + [game.successor(s, a, b) for a in (-1, 0, 1) for b in (-1, 0, 1)
                                  if game.successor(s, a, b) in game.values[1]],
            key=game.values[1].get)
        for s in live)
    print("first step of the greedy max-V1 walk -> states:", dict(greedy))
    modal = Counter()
    for s in live:
        while isinstance(s, tuple) and s[0] > 0:
            a1 = max(game.mixed(s, 1), key=game.mixed(s, 1).get)
            a2 = max(game.mixed(s, -1), key=game.mixed(s, -1).get)
            s = game.successor(s, a1, a2)
        modal[s if isinstance(s, str) else "crash"] += 1
    print("end of the most likely equilibrium trajectory -> states:", dict(modal))


def payoff_variants():
    quad_p = "crash_value_quadratic(state, -0.01, -1, 0)"
    quad_m = "crash_value_quadratic(state, -0.01, -1, -1)"
    linear = [(quad_p, "crash_value_quadratic(state, 0, -1, 0)"),
              (quad_m, "crash_value_quadratic(state, 0, -1, -1)")]
    no_reward = [("0.1*(A_p[i])", "0.0*(A_p[i])"), ("0.1*(A_m[j])", "0.0*(A_m[j])")]
    print("\n== Payoff variants (degeneracy check) ==")
    for name, patches in [("crash penalty linear in closing speed", linear),
                          ("no action reward", no_reward)]:
        ns, log, error = run_notebook(patches)
        # solve_game prints "d v1 v2" before each state; the check prints "degenerate".
        state, flagged = None, None
        for line in log.splitlines():
            if re.fullmatch(r"\d+ \d+ \d+", line):
                state = line
            elif line == "degenerate":
                flagged = state
                break
        solved = sum(1 for s in ns["values"][1] if isinstance(s, tuple) and s[0] > 0)
        print(f"{name}: degenerate at state {flagged}; "
              f"states solved before stopping: {solved}; error: {error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variants", action="store_true",
                        help="also re-solve with a linear crash penalty and with no action reward")
    parser.add_argument("--outdir", type=Path, default=PLOTS,
                        help="folder for the figures (default: plots/ next to this script)")
    args = parser.parse_args()

    if not NOTEBOOK.exists():
        raise SystemExit(f"Notebook not found: {NOTEBOOK}")
    ns, log, error = run_notebook()
    if error:
        raise SystemExit(f"The notebook cells failed: {error}")
    game = Game(ns)
    args.outdir.mkdir(parents=True, exist_ok=True)
    report_numbers(game, log)
    print("\n== Figures ==")
    for path in (figure_value_maps(game, args.outdir), figure_policy_maps(game, args.outdir)):
        print("wrote", os.path.relpath(path))
    if args.variants:
        payoff_variants()


if __name__ == "__main__":
    main()
