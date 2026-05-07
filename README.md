# Wumpus World: Knowledge-Based Autonomous Agent

An advanced implementation of the classic AI "Wumpus World" challenge, featuring an autonomous agent that navigates a hazardous grid using **Propositional Logic** and **Resolution Refutation**.



## 🚀 Key Features

- **Dynamic Environment:** Randomly generated 4x4 (or custom) grids with Pits and the Wumpus.
- **Inference Engine:** A custom-built resolution-based inference engine that proves cell safety.
- **KB Management:** Dynamic Knowledge Base (KB) maintained in Conjunctive Normal Form (CNF).
- **Autonomous Exploration:** The agent uses logic to explore only "provably safe" cells, avoiding hazards with 100% certainty when possible.
- **Real-time Metrics:** Tracks KB size, inference steps, and exploration progress.

## 🧠 Technical Deep Dive

### The Logic Engine
The core of this project is the **Resolution Refutation** algorithm. Unlike simple heuristic-based pathfinding, this agent *reasons* about its surroundings:
1. **Percept Processing:** Breeze and Stench percepts are converted into CNF clauses (e.g., `Breeze(1,1) ⇔ Pit(1,2) ∨ Pit(2,1)`).
2. **Knowledge Base:** The KB stores rules about the world and specific facts discovered during exploration.
3. **Safety Proofs:** For every potential move, the agent attempts to prove the negation of the hazard. If the KB derives a contradiction (empty clause) from `KB ∧ Hazard`, the cell is proven safe.

### Challenges Overcome
- **CNF Conversion:** Efficiently mapping biconditional rules into a minimal set of clauses.
- **Resolution Explosion:** Implementing a "visited" clause cache and step limits to ensure real-time performance without getting stuck in infinite resolution loops.
- **Teleportation Logic:** Using BFS to help the agent navigate back through visited "safe zones" to reach unexplored frontiers.

## 🛠️ Tech Stack

- **Backend:** Python, Flask (Inference Engine & API)
- **Frontend:** HTML5, Vanilla CSS, JavaScript (Visualizer)
- **Deployment:** Vercel (Serverless Functions)

## 💻 Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/wumpus-world-ai.git
   ```
2. **Install dependencies:**
   ```bash
   pip install flask flask-cors
   ```
3. **Run the server:**
   ```bash
   python app.py
   ```
4. **Access the UI:**
   Open `http://127.0.0.1:5000` in your browser.

## 📄 License
MIT License - feel free to use and modify for educational purposes.
