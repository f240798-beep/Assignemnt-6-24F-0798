"""
Wumpus World — Knowledge-Based Pathfinding Agent (Backend)

Flask server that manages:
  - Dynamic grid world with random pit/wumpus placement
  - Propositional logic Knowledge Base (CNF clauses)
  - Resolution Refutation inference engine
  - Autonomous agent that explores provably safe cells
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import random
import copy
import os
from itertools import combinations

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ═══════════════════════════════════════════════════════════════
#  Global State
# ═══════════════════════════════════════════════════════════════

rows = 4
cols = 4
world = {}          # (r,c) -> {"pit": bool, "wumpus": bool}
kb = []             # list of frozensets (CNF clauses)
visited = set()
agent_pos = (0, 0)
alive = True
game_over = False
inference_steps = 0
move_log = []
safe_cells = set()
unsafe_cells = set()  # cells proven to contain pit or wumpus
frontier = []         # stack for DFS-style exploration


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def neighbors(r, c):
    """Return valid neighbor coordinates."""
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            yield (nr, nc)


def pos_key(r, c):
    """Readable position string."""
    return f"({r},{c})"


# ═══════════════════════════════════════════════════════════════
#  World Initialization
# ═══════════════════════════════════════════════════════════════

def init_world(r=4, c=4):
    global rows, cols, world, kb, visited, agent_pos
    global alive, game_over, inference_steps, move_log
    global safe_cells, unsafe_cells, frontier

    rows = r
    cols = c
    world = {}
    kb = []
    visited = set()
    agent_pos = (0, 0)
    alive = True
    game_over = False
    inference_steps = 0
    move_log = []
    safe_cells = {(0, 0)}
    unsafe_cells = set()
    frontier = []

    # Build empty grid
    all_cells = [(i, j) for i in range(rows) for j in range(cols)]
    non_start = [cell for cell in all_cells if cell != (0, 0)]

    # Place pits (~20% of non-start cells, min 1, max half)
    num_pits = max(1, int(len(non_start) * 0.2))
    num_pits = min(num_pits, len(non_start) - 1)  # leave room for wumpus
    pit_cells = set(random.sample(non_start, num_pits))

    # Place wumpus on a non-start, non-pit cell
    wumpus_candidates = [cell for cell in non_start if cell not in pit_cells]
    if not wumpus_candidates:
        wumpus_candidates = non_start  # fallback
    wumpus_cell = random.choice(wumpus_candidates)

    for cell in all_cells:
        world[cell] = {
            "pit": cell in pit_cells,
            "wumpus": cell == wumpus_cell,
        }

    # Agent starts at (0,0) — mark as visited and tell KB
    visited.add((0, 0))
    _tell_visited(0, 0)
    _process_percepts(0, 0)


# ═══════════════════════════════════════════════════════════════
#  Percept Generation
# ═══════════════════════════════════════════════════════════════

def get_percepts(r, c):
    """Return percepts at (r, c) based on true world state."""
    breeze = False
    stench = False
    for nr, nc in neighbors(r, c):
        if world[(nr, nc)]["pit"]:
            breeze = True
        if world[(nr, nc)]["wumpus"]:
            stench = True
    return breeze, stench


# ═══════════════════════════════════════════════════════════════
#  Knowledge Base — TELL
# ═══════════════════════════════════════════════════════════════

def _add_clause(clause):
    """Add a CNF clause (frozenset of literals) to the KB, avoiding duplicates."""
    global kb
    fs = frozenset(clause)
    if fs and fs not in kb:
        kb.append(fs)


def _tell_visited(r, c):
    """When we visit (r,c) and survive, it's not a pit and not a wumpus."""
    _add_clause({f"~P_{r}_{c}"})
    _add_clause({f"~W_{r}_{c}"})


def _process_percepts(r, c):
    """
    Generate CNF clauses from percepts at (r,c).

    Breeze at (r,c):
        B_{r,c} ⇔ P_{n1} ∨ P_{n2} ∨ ...
        CNF of (B → P_n1 ∨ P_n2 ∨ ...): {P_n1, P_n2, ...}  (given B is true)
        CNF of (P_ni → B): already satisfied since B is true

    No Breeze at (r,c):
        ¬B_{r,c} ⇔ ¬P_{n1} ∧ ¬P_{n2} ∧ ...
        Each neighbor is definitely not a pit: {¬P_ni} for each ni

    Same logic for Stench / Wumpus.
    """
    breeze, stench = get_percepts(r, c)
    nbrs = list(neighbors(r, c))

    if breeze:
        # At least one neighbor is a pit
        _add_clause({f"P_{nr}_{nc}" for nr, nc in nbrs})
        # For each neighbor, if it's a pit then breeze here (tautological given breeze=true,
        # but useful for forward inference on other cells)
    else:
        # No breeze → no neighbor is a pit
        for nr, nc in nbrs:
            _add_clause({f"~P_{nr}_{nc}"})

    if stench:
        # At least one neighbor is the wumpus
        _add_clause({f"W_{nr}_{nc}" for nr, nc in nbrs})
    else:
        # No stench → no neighbor is wumpus
        for nr, nc in nbrs:
            _add_clause({f"~W_{nr}_{nc}"})


# ═══════════════════════════════════════════════════════════════
#  Resolution Refutation — ASK
# ═══════════════════════════════════════════════════════════════

def _resolve_pair(c1, c2):
    """
    Try to resolve two clauses on a single complementary literal.
    Returns the resolvent clause (frozenset) or None.
    """
    resolvents = []
    for lit in c1:
        comp = _complement(lit)
        if comp in c2:
            # Resolve on this literal
            new_clause = (c1 - {lit}) | (c2 - {comp})
            resolvents.append(frozenset(new_clause))

    # Only resolve on a single literal to avoid unsound resolution
    if len(resolvents) == 1:
        return resolvents[0]
    return None


def _complement(literal):
    """Return the complement of a literal: P ↔ ~P."""
    if literal.startswith("~"):
        return literal[1:]
    return f"~{literal}"


def _resolution_refutation(clauses_input, query_clause):
    """
    Use resolution refutation to determine if KB ⊨ query.

    To prove KB ⊨ ¬P_{r}_{c}:
      1. Add the negation of the query: {P_{r}_{c}}
      2. If we derive the empty clause → KB ⊨ ¬P_{r}_{c} (proven safe)

    Returns: (entailed: bool, steps: int)
    """
    global inference_steps

    clauses = list(set(clauses_input))  # deduplicate
    clauses.append(query_clause)
    clause_set = set(clauses)

    steps = 0
    max_steps = 5000  # safety limit

    new = set()

    while steps < max_steps:
        pairs = list(combinations(clauses, 2))
        found_new = False

        for ci, cj in pairs:
            resolvent = _resolve_pair(ci, cj)
            steps += 1
            inference_steps += 1

            if resolvent is not None:
                # Empty clause → contradiction → query is entailed
                if len(resolvent) == 0:
                    return True, steps

                if resolvent not in clause_set:
                    new.add(resolvent)
                    found_new = True

            if steps >= max_steps:
                break

        if not found_new:
            return False, steps

        for c in new:
            if c not in clause_set:
                clauses.append(c)
                clause_set.add(c)
        new = set()

    return False, steps


def is_cell_safe(r, c):
    """
    ASK the KB whether cell (r,c) is safe.
    Proves both ¬P_{r}_{c} and ¬W_{r}_{c} via resolution refutation.
    """
    if (r, c) in visited:
        return True

    kb_copy = list(kb)

    # Prove ¬P_{r}_{c}: negate it → add {P_{r}_{c}} and look for contradiction
    no_pit, pit_steps = _resolution_refutation(
        list(kb_copy), frozenset({f"P_{r}_{c}"})
    )

    # Prove ¬W_{r}_{c}: negate it → add {W_{r}_{c}} and look for contradiction
    no_wumpus, wumpus_steps = _resolution_refutation(
        list(kb_copy), frozenset({f"W_{r}_{c}"})
    )

    return no_pit and no_wumpus


def is_cell_dangerous(r, c, hazard_type="P"):
    """
    ASK the KB whether cell (r,c) definitely contains a hazard.
    Proves P_{r}_{c} (or W_{r}_{c}) via resolution refutation.
    """
    prefix = hazard_type
    kb_copy = list(kb)

    # Prove P_{r}_{c}: negate it → add {~P_{r}_{c}} and look for contradiction
    entailed, _ = _resolution_refutation(
        list(kb_copy), frozenset({f"~{prefix}_{r}_{c}"})
    )
    return entailed


# ═══════════════════════════════════════════════════════════════
#  Agent — Autonomous Stepping
# ═══════════════════════════════════════════════════════════════

def _classify_cells():
    """Update safe_cells and unsafe_cells based on current KB."""
    global safe_cells, unsafe_cells

    for r in range(rows):
        for c in range(cols):
            if (r, c) in visited:
                safe_cells.add((r, c))
                continue
            if (r, c) in safe_cells or (r, c) in unsafe_cells:
                continue

            # Only check cells adjacent to visited cells (the frontier)
            is_adjacent_to_visited = any(
                n in visited for n in neighbors(r, c)
            )
            if not is_adjacent_to_visited:
                continue

            if is_cell_safe(r, c):
                safe_cells.add((r, c))
            elif is_cell_dangerous(r, c, "P") or is_cell_dangerous(r, c, "W"):
                unsafe_cells.add((r, c))


def agent_step():
    """
    Advance the agent by one cell.
    Strategy:
      1. Classify frontier cells as safe/unsafe
      2. Among unvisited safe neighbors of current position, pick one
      3. If none, BFS through visited cells to find one with an unvisited safe neighbor
      4. If truly stuck, stop
    """
    global agent_pos, alive, game_over, move_log

    if game_over:
        return _build_state("Game is already over.")

    # Classify what we can
    _classify_cells()

    # Try unvisited safe neighbors of current position first
    target = None
    cr, cc = agent_pos

    unvisited_safe_nbrs = [
        n for n in neighbors(cr, cc)
        if n not in visited and n in safe_cells
    ]
    if unvisited_safe_nbrs:
        target = unvisited_safe_nbrs[0]

    # If no direct neighbor, BFS through visited cells
    if target is None:
        target, path = _bfs_to_unvisited_safe()
        if target is None:
            game_over = True
            msg = "Agent has explored all reachable safe cells. Exploration complete!"
            move_log.append(msg)
            return _build_state(msg)
        # Move along path: move agent to the cell adjacent to target
        # (we teleport through visited cells for simplicity — each step just moves one cell)
        if path:
            # Move to next cell on the path
            target = path[0]

    # --- Execute the move ---
    r, c = target
    agent_pos = (r, c)
    visited.add((r, c))

    # Check if agent stepped on a hazard
    if world[(r, c)]["pit"]:
        alive = False
        game_over = True
        msg = f"Agent fell into a PIT at {pos_key(r, c)}! Game Over."
        move_log.append(msg)
        return _build_state(msg)

    if world[(r, c)]["wumpus"]:
        alive = False
        game_over = True
        msg = f"Agent was eaten by the WUMPUS at {pos_key(r, c)}! Game Over."
        move_log.append(msg)
        return _build_state(msg)

    # Tell KB about new visit
    _tell_visited(r, c)
    _process_percepts(r, c)

    # Re-classify after new knowledge
    _classify_cells()

    breeze, stench = get_percepts(r, c)
    percept_str = []
    if breeze:
        percept_str.append("Breeze")
    if stench:
        percept_str.append("Stench")
    percept_msg = ", ".join(percept_str) if percept_str else "None"

    msg = f"Moved to {pos_key(r, c)}. Percepts: {percept_msg}"
    move_log.append(msg)

    # Check if all safe cells explored
    unexplored_safe = safe_cells - visited
    if not unexplored_safe:
        # Check if there are still unknown frontier cells
        has_unknown_frontier = False
        for vr, vc in visited:
            for nr, nc in neighbors(vr, vc):
                if (nr, nc) not in visited and (nr, nc) not in unsafe_cells:
                    if (nr, nc) not in safe_cells:
                        has_unknown_frontier = True
                        break
            if has_unknown_frontier:
                break

        if not has_unknown_frontier:
            game_over = True
            msg += " — All reachable safe cells explored!"

    return _build_state(msg)


def _bfs_to_unvisited_safe():
    """
    BFS from agent_pos through visited cells to find a visited cell
    that has an unvisited safe neighbor. Returns (target, path).
    """
    from collections import deque

    start = agent_pos
    queue = deque([(start, [])])
    seen = {start}

    while queue:
        (cr, cc), path = queue.popleft()

        for nr, nc in neighbors(cr, cc):
            if (nr, nc) in visited and (nr, nc) not in seen:
                seen.add((nr, nc))
                queue.append(((nr, nc), path + [(nr, nc)]))
            elif (nr, nc) not in visited and (nr, nc) in safe_cells:
                # Found an unvisited safe cell reachable via visited cells
                return (nr, nc), path + [(nr, nc)]

    return None, []


# ═══════════════════════════════════════════════════════════════
#  State Builder
# ═══════════════════════════════════════════════════════════════

def _build_state(message=""):
    """Build the full state response for the frontend."""
    breeze, stench = get_percepts(*agent_pos) if alive else (False, False)

    grid = {}
    for r in range(rows):
        for c in range(cols):
            key = f"{r},{c}"
            if (r, c) == agent_pos:
                grid[key] = "agent"
            elif (r, c) in visited:
                grid[key] = "visited"
            elif (r, c) in safe_cells:
                grid[key] = "safe"
            elif (r, c) in unsafe_cells:
                grid[key] = "danger"
            else:
                grid[key] = "unknown"

    # Reveal hazards on game over
    hazard_map = {}
    for r in range(rows):
        for c in range(cols):
            key = f"{r},{c}"
            h = []
            if world[(r, c)]["pit"]:
                h.append("pit")
            if world[(r, c)]["wumpus"]:
                h.append("wumpus")
            if h:
                hazard_map[key] = h

    # Percept map for visited cells
    percept_map = {}
    for vr, vc in visited:
        b, s = get_percepts(vr, vc)
        percs = []
        if b:
            percs.append("breeze")
        if s:
            percs.append("stench")
        if percs:
            percept_map[f"{vr},{vc}"] = percs

    return {
        "rows": rows,
        "cols": cols,
        "agent": list(agent_pos),
        "alive": alive,
        "game_over": game_over,
        "grid": grid,
        "hazards": hazard_map if game_over else {},
        "percepts": {"breeze": breeze, "stench": stench},
        "percept_map": percept_map,
        "inference_steps": inference_steps,
        "kb_size": len(kb),
        "visited_count": len(visited),
        "total_cells": rows * cols,
        "message": message,
        "log": move_log[-20:],  # last 20 entries
    }


# ═══════════════════════════════════════════════════════════════
#  Flask API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.route("/reset", methods=["POST"])
def reset():
    """Initialize a new world. Body: {rows: int, cols: int}"""
    data = request.get_json(silent=True) or {}
    r = int(data.get("rows", 4))
    c = int(data.get("cols", 4))
    r = max(3, min(r, 10))
    c = max(3, min(c, 10))
    init_world(r, c)
    return jsonify(_build_state("New world created. Agent at (0,0)."))


@app.route("/step", methods=["POST"])
def step():
    """Advance the agent by one cell."""
    return jsonify(agent_step())


@app.route("/state", methods=["GET"])
def state():
    """Return current full state."""
    return jsonify(_build_state())


@app.route("/")
def serve_index():
    """Serve the frontend HTML."""
    return send_from_directory('.', "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    """Serve static files (CSS, JS)."""
    return send_from_directory('.', filename)


# ═══════════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5000)