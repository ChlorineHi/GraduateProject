import { useEffect, useRef } from "react";
import type { Frame } from "./api";

// Grid canvas only. YJMob stays on its anonymous virtual grid and is never drawn on a geographic basemap.

const ZONE: Record<string, string> = {
  residential: "#d7c4a3",
  commercial: "#c98455",
  arterial: "#8d5a45",
  industrial: "#6d6258",
  park: "#7ea184",
  school: "#d2b15a",
};

function mix(t: number) {
  const stops = [
    [23, 52, 48],
    [29, 107, 94],
    [214, 186, 122],
    [196, 112, 62],
    [164, 52, 40],
  ];
  const x = Math.min(0.999, Math.max(0, t)) * (stops.length - 1);
  const i = Math.floor(x);
  const f = x - i;
  const a = stops[i];
  const b = stops[Math.min(stops.length - 1, i + 1)];
  const c = a.map((value, index) => Math.round(value + (b[index] - value) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

function scale(value: number, min: number, max: number) {
  return (value - min) / Math.max(0.001, max - min);
}

export function CityMap({
  frame,
  mode,
  showPeople,
  showTasks,
  showObs,
  selected,
  onSelect,
}: {
  frame: Frame;
  mode: "prediction" | "uncertainty" | "zone" | "truth";
  showPeople: boolean;
  showTasks: boolean;
  showObs: boolean;
  selected: { x: number; y: number } | null;
  onSelect: (cell: Frame["cells"][number]) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const width = canvas.clientWidth;
    const height = Math.max(320, Math.round(width * (frame.height / frame.width)));
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const pad = 16;
    const cell = Math.min((width - pad * 2) / frame.width, (height - pad * 2) / frame.height);
    const ox = (width - cell * frame.width) / 2;
    const oy = (height - cell * frame.height) / 2;
    const values = frame.cells.map((cellItem) => {
      if (mode === "uncertainty") return cellItem.uncertainty;
      if (mode === "truth") return cellItem.truth ?? cellItem.prediction;
      return cellItem.prediction;
    });
    const min = mode === "zone" ? 0 : Math.min(...values);
    const max = mode === "zone" ? 1 : Math.max(...values);
    for (const item of frame.cells) {
      let fill = ZONE[item.zone] || "#ccc";
      if (mode === "prediction") fill = mix(scale(item.prediction, 32, 80));
      if (mode === "truth" && item.truth !== undefined) fill = mix(scale(item.truth, 32, 80));
      if (mode === "uncertainty") fill = mix(scale(item.uncertainty, min, max));
      ctx.fillStyle = fill;
      ctx.fillRect(ox + item.x * cell, oy + item.y * cell, cell - 1, cell - 1);
    }
    if (showObs) {
      ctx.fillStyle = "#17231d";
      for (const obs of frame.observations) {
        ctx.fillRect(ox + obs.x * cell + cell * 0.3, oy + obs.y * cell + cell * 0.3, Math.max(3, cell * 0.35), Math.max(3, cell * 0.35));
      }
    }
    if (showTasks) {
      ctx.strokeStyle = "#b64032";
      ctx.lineWidth = 2;
      for (const task of frame.tasks) {
        ctx.strokeRect(ox + task.x * cell + 1, oy + task.y * cell + 1, cell - 3, cell - 3);
      }
    }
    if (showPeople) {
      for (const person of frame.participants) {
        ctx.beginPath();
        ctx.fillStyle = person.kind === "machine" ? "#1d6b5d" : "#17231d";
        ctx.arc(ox + (person.x + 0.5) * cell, oy + (person.y + 0.5) * cell, Math.max(3, cell * 0.18), 0, Math.PI * 2);
        ctx.fill();
      }
    }
    if (selected) {
      ctx.strokeStyle = "#f7f1e4";
      ctx.lineWidth = 2;
      ctx.strokeRect(ox + selected.x * cell, oy + selected.y * cell, cell - 1, cell - 1);
    }
    canvas.onclick = (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = Math.floor((event.clientX - rect.left - ox) / cell);
      const y = Math.floor((event.clientY - rect.top - oy) / cell);
      const found = frame.cells.find((item) => item.x === x && item.y === y);
      if (found) selectRef.current(found);
    };
  }, [frame, mode, showPeople, showTasks, showObs, selected]);
  return <canvas ref={ref} />;
}
