import csv
import random

# Set seed for exact reproducibility matching playbook: Drug B mean ~94.8, control ~91.2, delta +3.6
random.seed(42)

treatments = ["Control", "Drug A", "Drug B", "Drug C"]
doses = [10.0, 50.0, 100.0]
timepoints = [24, 48, 72]
cell_lines = ["HeLa", "A549"]

rows = []
sample_idx = 1

# Base distribution functions
def get_viability(treatment, dose, timepoint):
    if treatment == "Control":
        base = 91.2
        noise = random.gauss(0, 1.8)
        return round(max(85.0, min(97.0, base + noise)), 1)
    elif treatment == "Drug A":
        # Cytotoxic: decreases with dose and time
        base = 90.0 - (dose * 0.45) - ((timepoint - 24) * 0.2)
        noise = random.gauss(0, 2.2)
        return round(max(20.0, min(95.0, base + noise)), 1)
    elif treatment == "Drug B":
        # High viability / cytoprotective: ~94.8% mean
        base = 94.8 + ((dose - 50) * 0.02)
        noise = random.gauss(0, 1.6)
        return round(max(91.0, min(99.0, base + noise)), 1)
    elif treatment == "Drug C":
        # Mild inhibition
        base = 88.0 - (dose * 0.08)
        noise = random.gauss(0, 2.0)
        return round(max(70.0, min(94.0, base + noise)), 1)

# Generate combinations
# 4 treatments x 3 doses x 3 timepoints x 3 replicates = 108 rows
# We need exactly 127 observations to match the PRD spec: "127 observations, 4 treatments, 3 doses, 3 replicates"
# Add 19 additional replicates across early timepoints/controls

for t in treatments:
    t_doses = [0.0] if t == "Control" else doses
    for d in t_doses:
        for tp in timepoints:
            for rep in [1, 2, 3]:
                cell = "HeLa" if (sample_idx % 2 == 1) else "A549"
                v = get_viability(t, d, tp)
                rows.append({
                    "sample_id": f"SMP-{sample_idx:04d}",
                    "cell_line": cell,
                    "treatment": t,
                    "dose": d,
                    "timepoint": tp,
                    "replicate": rep,
                    "viability": v
                })
                sample_idx += 1

# Add remaining rows to reach exactly 127
while len(rows) < 127:
    t = random.choice(treatments)
    d = 0.0 if t == "Control" else random.choice(doses)
    tp = random.choice(timepoints)
    rep = (len(rows) % 3) + 1
    cell = "HeLa" if (sample_idx % 2 == 1) else "A549"
    v = get_viability(t, d, tp)
    rows.append({
        "sample_id": f"SMP-{sample_idx:04d}",
        "cell_line": cell,
        "treatment": t,
        "dose": d,
        "timepoint": tp,
        "replicate": rep,
        "viability": v
    })
    sample_idx += 1

rows = rows[:127]

import os
os.makedirs("data", exist_ok=True)
with open("data/synthetic_viability.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["sample_id", "cell_line", "treatment", "dose", "timepoint", "replicate", "viability"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} observations in data/synthetic_viability.csv")
