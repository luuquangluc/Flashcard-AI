"use client"

import * as React from "react"

interface RadarMetric {
  label: string;
  value: number; // 0 to 100
  fullMark: number;
}

interface RadarChartProps {
  data: RadarMetric[];
  size?: number;
  color?: string;
}

export function RadarChart({ data, size = 300, color = "hsl(var(--primary))" }: RadarChartProps) {
  const padding = 40;
  const radius = (size - padding * 2) / 2;
  const center = size / 2;
  const angleStep = (Math.PI * 2) / data.length;

  // Generate points for the background polygons
  const backgroundLevels = [0.2, 0.4, 0.6, 0.8, 1];
  
  const getPoint = (index: number, ratio: number) => {
    const angle = index * angleStep - Math.PI / 2;
    const r = radius * ratio;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle)
    };
  };

  const points = data.map((d, i) => getPoint(i, d.value / 100));
  const polygonPath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ") + " Z";

  return (
    <div className="flex flex-col items-center justify-center relative select-none">
      <svg width={size} height={size} className="overflow-visible">
        {/* Background Grids */}
        {backgroundLevels.map((level, i) => {
          const gridPoints = data.map((_, j) => getPoint(j, level));
          const path = gridPoints.map((p, k) => `${k === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ") + " Z";
          return (
            <path
              key={i}
              d={path}
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
              className="text-border/40"
            />
          );
        })}

        {/* Axis Lines */}
        {data.map((_, i) => {
          const p = getPoint(i, 1);
          return (
            <line
              key={i}
              x1={center}
              y1={center}
              x2={p.x}
              y2={p.y}
              stroke="currentColor"
              strokeWidth="1"
              strokeDasharray="4 4"
              className="text-border/40"
            />
          );
        })}

        {/* Data Polygon */}
        <path
          d={polygonPath}
          fill={color}
          fillOpacity="0.15"
          stroke={color}
          strokeWidth="3"
          strokeLinejoin="round"
          className="transition-all duration-1000 ease-out"
        />

        {/* Data Points */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r="4"
            fill="white"
            stroke={color}
            strokeWidth="2"
            className="transition-all duration-1000 ease-out"
          />
        ))}

        {/* Labels */}
        {data.map((d, i) => {
          const p = getPoint(i, 1.15);
          return (
            <text
              key={i}
              x={p.x}
              y={p.y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="text-[10px] font-bold uppercase tracking-widest fill-muted-foreground"
            >
              {d.label}
            </text>
          );
        })}
      </svg>
      
      {/* Central Stats Summary */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="bg-background/80 backdrop-blur-sm border border-border/50 rounded-full w-16 h-16 flex items-center justify-center shadow-sm">
             <span className="text-xl font-black text-primary">
                {Math.round(data.reduce((acc, d) => acc + d.value, 0) / data.length)}
             </span>
        </div>
      </div>
    </div>
  );
}
