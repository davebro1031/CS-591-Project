# Chicken Game Project

This repository contains two things:

- `chicken.ipynb`, a notebook that solves a two-player game of chicken, computes state values with Gambit (`pygambit`), and plots the value function: a static Matplotlib 3D scatter, an interactive Plotly 3D landscape, and a Plotly heatmap with a distance slider.
- `make_report_figures.py`, a script that runs the notebook's model and solver and regenerates the figures and numbers of the final report. It writes the figures to a `plots/` folder (see [section 4](#4-regenerate-the-report-figures-and-numbers)).

## Requirements

- **Python 3.10–3.12** (3.12 is tested). Newer versions such as 3.14 may not have working `pygambit` wheels.
- `pip`
- A C++ toolchain if `pygambit` has to build from source:
  - macOS: `xcode-select --install`
  - Ubuntu/Debian: `sudo apt install build-essential`

## 1. Create a virtual environment

Clone the repository and create the environment inside it:

```bash
git clone https://github.com/davebro1031/CS-591-Project.git
cd CS-591-Project
python3.12 -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` in the terminal prompt.

## 2. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

This installs NumPy, SciPy, pandas, Matplotlib, NetworkX, pygambit, Plotly, `ipykernel`, and `nbformat`.

Register a Jupyter kernel that points at this environment:

```bash
python -m ipykernel install --user --name chicken --display-name "Python (chicken)"
```

## 3. Run the notebook

Always select the **`.venv` / Python (chicken)** kernel, then run cells **from top to bottom**. Before any figure, you need:

1. `solve_game()` — fills `values` and `strats`
2. The `arr_to_dict` / `strats_nice` cell — labels mixed strategies
3. The visualization cells, in order (helpers + Matplotlib, then Plotly 3D, then the heatmap)

### JupyterLab

Install JupyterLab in the same environment (one time):

```bash
python -m pip install jupyterlab
jupyter lab chicken.ipynb
```

In the notebook toolbar, open the kernel picker and choose **Python (chicken)** (or the interpreter whose path is this folder's `.venv`).

Install and launch JupyterLab from this `.venv`, with the environment activated. Plotly ships its JupyterLab renderer (`jupyterlab-plotly`) inside the environment where Plotly is installed. If you start a JupyterLab that lives in a different environment and only point the kernel at `.venv`, the two Plotly figures may come up blank. The solver and the Matplotlib plot still work in that case.

### VS Code

1. Install the **Python** and **Jupyter** extensions.
2. Open this repository folder in VS Code.
3. Open `chicken.ipynb`.
4. Click **Select Kernel** in the top right.
5. Choose **Python Environments**, then `.venv` (Python 3.12).
   - If it does not appear: Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) → **Python: Select Interpreter** → **Enter interpreter path…** → select `.venv/bin/python` (macOS/Linux) or `.venv\Scripts\python.exe` (Windows).
6. Run All, or run cells in order.

### Cursor

Cursor uses the same kernel flow as VS Code.

1. Open the folder in Cursor.
2. Open `chicken.ipynb`.
3. Click **Select Kernel** (or Command Palette → **Notebook: Select Notebook Kernel**).
4. Pick **Python Environments** (not a Jupyter kernelspec name). Select `.venv`.
5. If the list is empty, use **Python: Select Interpreter** and paste the full path to `.venv/bin/python`.
6. Run cells from the top.

The kernel name in the UI is usually **`.venv (Python 3.12.x)`**, not the word “chicken”. That is the correct environment.

## 4. Regenerate the report figures and numbers

`make_report_figures.py` executes the notebook's model and solver cells unchanged (every code cell above the "Visualizations" heading) and then computes the results quoted in the final report. It does not need Jupyter or a registered kernel, only the environment from steps 1 and 2.

With the environment activated, from this folder:

```bash
python make_report_figures.py             # figures and numbers
python make_report_figures.py --variants  # also re-solve two payoff variants
```

It takes a few seconds. The figures go to a `plots/` folder next to the script, which is created if it does not exist:

| File | Content |
| --- | --- |
| `plots/value_maps.pdf` | Equilibrium values of both players for every speed pair, at last-decision states and at the initial distance `d = 9` |
| `plots/policy_maps.pdf` | Probability that each player swerves, and probability of a crash, for every speed pair |

Use `--outdir some/folder` to write the figures somewhere else.

The script prints the numbers used in the report: state counts, the range of values and swerve probabilities, the probability of each outcome under the equilibrium policies, a closed-form check of the mixed equilibrium, and the reachability results (possible win, sure win, sure crash avoidance).

With `--variants`, the last two lines end in `error: TypeError: ...`. That is the expected result, not a failure of the script: it reports that the notebook's solver stops at a degenerate state when the crash penalty is linear or the action reward is removed.

## 5. What the notebook does

A state is `(d, v+, v-)`: remaining distance and the two speeds. Color in every plot is player `+`'s continuation value \(V_+\).

| Cells | Purpose |
| --- | --- |
| Imports and payoffs | Crash / swerve values, action sets |
| Dynamics and helpers | Transition kernel, expected values, equilibrium extraction |
| `solve_game()` | Fills `values` and `strats` for reachable states |
| Printing / `strats_nice` | Inspect values and label mixed strategies |
| Visualizations | Matplotlib 3D, Plotly 3D, Plotly heatmap (see below) |

### Plots

**Matplotlib 3D (static).** Every numeric state as a point colored by \(V_+\). The black path starts at `(9, 6, 6)` and at each step moves to a successor with the **largest \(V_+\)**. That greedy walk is a snapshot of the value landscape, not mixed-strategy equilibrium play.

**Plotly 3D (interactive).** Same axes, with:

| Marker | Meaning |
| --- | --- |
| Diamond | Crash (`d = 0`) |
| Square | At least one player swerves with probability ≥ 0.5 |
| Circle | Other in-motion states |
| Black path | Modal equilibrium trajectory through `kernel` |

Hover a point for both players' values, mixed strategies (`swerve` / `do nothing` / `speed up` / `slow down`), and swerve probabilities. Use the **Start state** dropdown to pick `(d, v+, v-)`. The path uses each player's highest-probability action. Swerve terminals `s+`, `s-`, `s0` appear in hover as `next = ...`; they are not 3D coordinates. Drag to rotate the view.

**Plotly heatmap.** A \(v_+ \times v_-\) slice of \(V_+\) at one distance. Drag the **\(d\)** slider from crash (`d = 0`) to the farthest solved gap. Hover a cell for \(V_+\), \(V_-\), and both mixed strategies.

Markdown cells above each figure in the notebook repeat this legend.

## 6. Findings and suggested next steps

### Can either player force a win?

No. Take "win" to mean the opponent swerves alone (`s-` for player `+`, `s+` for player `−`). A sure-win reachability check on the transition kernel gives:

| Objective | States where it can be forced (of 144 with `d > 0`) |
| --- | --- |
| `+` forces `s-` (only `−` swerves) | 0 |
| `−` forces `s+` (only `+` swerves) | 0 |
| Either player forces "no crash" | 144 |

Swerving is voluntary, so the opponent can always refuse. The only outcomes left are your own swerve or a crash. This follows from `kernel` alone, so it holds for any payoffs, and randomizing does not help: the win probability a player can guarantee is 0.

What each player can guarantee is safety. Swerving immediately gives `+` at least −5 and `−` at least −2.

The game is also short. With `d ≤ 9` and `v_min = 3`, every play ends within two joint moves, and only 10 of the 144 states have a second decision.

`make_report_figures.py` reproduces this check (see section 4). It is not a notebook cell.

### Analyses worth adding

1. **Outcome probabilities under equilibrium, in the notebook.** `make_report_figures.py` already pushes the mixed strategies through `kernel` to get P(crash), P(`+` wins), P(`−` wins) and P(both swerve) from each start state. A notebook cell could show the same numbers in place of the modal-action trajectory, which discards the probabilities.
2. **Security level versus equilibrium value.** For each state, compare what a player can guarantee with what equilibrium play gives them.
3. **Payoff sensitivity.** Sweep the crash penalty and the swerve payoffs to find where P(crash) goes to 0, or where one player always swerves.

### Model changes that would make the analysis richer

Changing the speeds or the distance does not make a win forcible against an adversarial opponent. The argument above only needs the opponent to be able to decline to swerve.

- **Braking to a stop** (`v_min = 0`) and **more rounds** (a longer starting distance or lower speeds). Plays get many decisions, so the timing of a swerve matters, and "from which states can both cars still stop in time" becomes a region worth computing.
- **Commitment or turn-based moves.** A player who commits first can force a *rational* opponent to swerve. That is winning against a payoff-maximizing opponent, not an adversarial one, so any write-up should say which notion it uses.

### Solver issues to fix first

- `solve_game` picks a random equilibrium with no seed and drops pure equilibria when several exist. Values at `d = 7..9` build on those picks, so they can change between runs. Set a seed, or choose the equilibrium by a fixed rule.
- If a state has several equilibria and none is mixed, or `evaluate_state` returns `None` (degenerate or unmatched solvers), `solve_game` raises an error. This has not come up in runs so far.

## Troubleshooting

**`No module named 'pygambit'` / `'plotly'` / `'nbformat'`**  
The notebook is not using this virtual environment. Select the `.venv` kernel and rerun the import cell.

**`Mime type rendering requires nbformat>=4.2.0`**  
Plotly needs `nbformat` in the same environment:

```bash
python -m pip install "nbformat>=4.2.0"
```

Restart the kernel, then rerun the Plotly cells.

**Plotly figures are blank in JupyterLab**  
JupyterLab is probably running from a different environment than `.venv`, so it cannot find Plotly's renderer. Install and start it from the activated `.venv`:

```bash
source .venv/bin/activate
python -m pip install jupyterlab
jupyter lab chicken.ipynb
```

Then refresh the browser tab and rerun the Plotly cells.

**`pygambit` fails to install**  
Use Python 3.12, not 3.9 or 3.14. If pip builds from source, install a C++ compiler (see Requirements) and retry:

```bash
python -m pip install pygambit
```

**Kernel picker does not show `.venv`**  
Use **Python: Select Interpreter** → **Enter interpreter path…** and choose `.venv/bin/python` in this folder. Reload the window if needed.

**Plots are empty or `KeyError` on `values[1]` / `strats_nice`**  
Run `solve_game()`, then the `strats_nice` cell, then the visualization cells in order. Do not skip earlier cells after a kernel restart.

**Plotly 3D dropdown does not change the path**  
Re-run the Plotly 3D cell after `strats_nice` exists. The dropdown restyles the black trajectory trace only.

## Recreate the environment from scratch

From this folder:

```bash
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m ipykernel install --user --name chicken --display-name "Python (chicken)"
```
