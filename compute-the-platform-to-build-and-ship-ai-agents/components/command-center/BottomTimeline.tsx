"use client";

import React, { useState } from 'react';
import { useMissionStore } from '@/lib/useMissionStore';
import { 
  CheckCircle2, 
  Circle, 
  Clock, 
  Terminal, 
  ChevronUp, 
  ChevronDown, 
  Activity,
  Layers,
  Cpu
} from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';

export const BottomTimeline: React.FC = () => {
  const { activeJob } = useMissionStore();
  const [isLogOpen, setIsLogOpen] = useState(false);

  const stages = [
    { id: 1, name: "Stage 1", label: "Ingestion & Sync", desc: "SRT/KLV Geodetic UTM" },
    { id: 2, name: "Stage 2", label: "Keyframe Gating", desc: "Laplacian Blur & Parallax" },
    { id: 3, name: "Stage 3", label: "Foundation ViT", desc: "Pointmaps & Kabsch SVD" },
    { id: 4, name: "Stage 4", label: "Sim(3) Georef", desc: "Umeyama DOP Scaling" },
    { id: 5, name: "Stage 5", label: "Surface 3DGS & SDF", desc: "Watertight Meshing" },
    { id: 6, name: "Stage 6", label: "Audit & Exporters", desc: "LAS, glTF, DSM GeoTIFF" },
  ];

  const currentStageName = activeJob?.stage || 'COMPLETED';
  const progressPct = activeJob?.progress_pct ?? 100;

  // Derive which stages are completed
  const currentStageNum = currentStageName.includes('Stage 1')
    ? 1
    : currentStageName.includes('Stage 2')
    ? 2
    : currentStageName.includes('Stage 3')
    ? 3
    : currentStageName.includes('Stage 4')
    ? 4
    : currentStageName.includes('Stage 5')
    ? 5
    : currentStageName.includes('Stage 6')
    ? 6
    : 6;

  const logs = [
    "[INFO] Telemetry synchronized: 9 keyframes anchored to WGS84 UTM Zone 43N",
    "[INFO] Laplacian blur detector: filtered 14 blurry frames, 9 passed gate",
    "[INFO] ViT foundation pointmap regression completed: 250,000 dense points",
    "[INFO] Weighted Umeyama Sim(3) alignment solved: scale s=1.0053, RMSE=0.42m",
    "[INFO] Surface-aligned 3DGS converged: 12,000 planar Gaussians",
    "[INFO] Marching Cubes SDF extraction: 100% Watertight Manifold (Euler = 2)",
    "[SUCCESS] Deliverables generated: glTF 2.0, LAS 1.4, GeoTIFF DSM, Audit Report",
  ];

  return (
    <div className="border-t border-cyan-500/20 bg-slate-950/95 backdrop-blur-md text-white font-mono select-none z-20">
      {/* Collapsible Log Terminal */}
      {isLogOpen && (
        <div className="h-32 border-b border-slate-800 bg-[#030712] p-3 text-xs overflow-y-auto">
          <div className="flex items-center justify-between text-slate-400 mb-1.5 pb-1 border-b border-slate-800">
            <span className="flex items-center gap-1 text-cyan-400 font-bold">
              <Terminal className="w-3.5 h-3.5" />
              PIPELINE EXECUTION LOGS
            </span>
            <span className="text-[10px]">Real-time stdout</span>
          </div>
          <div className="space-y-1 font-mono text-[11px]">
            {logs.map((log, i) => (
              <div key={i} className="text-slate-300">
                <span className="text-cyan-500 mr-1.5">›</span>
                {log}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Stepper Bar */}
      <div className="px-4 py-2.5 flex items-center justify-between gap-4">
        {/* Left: Overall Status & Toggle */}
        <div className="flex items-center gap-3 min-w-[200px]">
          <button
            onClick={() => setIsLogOpen(!isLogOpen)}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-cyan-300 transition-colors"
          >
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>LOGS</span>
            {isLogOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
          </button>

          <div className="h-4 w-[1px] bg-slate-800" />

          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400">PIPELINE:</span>
            <Badge className="bg-emerald-950 text-emerald-400 border border-emerald-500/30 text-[10px] px-1.5 py-0">
              {progressPct >= 100 ? 'READY' : `${progressPct}%`}
            </Badge>
          </div>
        </div>

        {/* Middle: 6 Interactive Stage Nodes */}
        <div className="flex-1 grid grid-cols-6 gap-2">
          {stages.map((stage) => {
            const isCompleted = progressPct >= 100 || currentStageNum > stage.id;
            const isCurrent = currentStageNum === stage.id && progressPct < 100;

            return (
              <div
                key={stage.id}
                className={`p-1.5 rounded border text-left transition-all ${
                  isCurrent
                    ? 'bg-cyan-950/40 border-cyan-500 text-cyan-200 shadow-sm shadow-cyan-500/30'
                    : isCompleted
                    ? 'bg-slate-900/60 border-emerald-500/30 text-slate-300'
                    : 'bg-slate-950/40 border-slate-800 text-slate-600'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-slate-400">
                    {stage.name}
                  </span>
                  {isCompleted ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  ) : isCurrent ? (
                    <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                  ) : (
                    <Circle className="w-2.5 h-2.5 text-slate-700" />
                  )}
                </div>
                <div className="text-[11px] font-semibold truncate text-slate-200 mt-0.5">
                  {stage.label}
                </div>
                <div className="text-[9px] text-slate-500 truncate">
                  {stage.desc}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: Runtime info */}
        <div className="hidden xl:flex items-center gap-3 text-xs text-slate-400 min-w-[150px] justify-end">
          <div className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>TOTAL TIME:</span>
            <span className="text-slate-200 font-bold">6.7s</span>
          </div>
        </div>
      </div>
    </div>
  );
};
