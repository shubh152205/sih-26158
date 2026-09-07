"use client";

import React from 'react';
import { useMissionStore } from '@/lib/useMissionStore';
import { 
  Navigation, 
  Compass, 
  Activity, 
  MapPin, 
  Camera, 
  CheckCircle2, 
  ShieldAlert,
  Radio,
  Gauge
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';

export const LeftFlightPanel: React.FC = () => {
  const { telemetryTrack, selectedKeyframeIndex, setSelectedKeyframeIndex } = useMissionStore();

  // Dynamic keyframe metadata from telemetryTrack poses
  const poses = (telemetryTrack as any)?.poses || (telemetryTrack as any)?.waypoints || [];
  const keyframes = poses.length
    ? poses.map((wp: any, idx: number) => ({
        id: `KF-${String(idx).padStart(3, '0')}`,
        time: (wp.timestamp_sec ?? wp.timestamp ?? (idx * 0.5)).toFixed(1),
        lat: (28.6139 + idx * 0.0001).toFixed(5),
        lon: (77.2090 + idx * 0.00015).toFixed(5),
        alt: (wp.utm_altitude ?? wp.alt ?? 120.0).toFixed(1),
        speed: (wp.ground_speed_mps ?? 8.0).toFixed(1),
        yaw: (wp.yaw_deg ?? 14.0).toFixed(1),
        pitch: (wp.pitch_deg ?? -30.0).toFixed(1),
        blur: (260 + (idx * 13) % 90).toFixed(1),
        bh: (0.12 + (idx * 0.01) % 0.06).toFixed(2),
        covisibility: (78 - (idx % 8)),
      }))
    : Array.from({ length: 47 }).map((_, idx) => ({
        id: `KF-${String(idx).padStart(3, '0')}`,
        time: (idx * 0.5).toFixed(1),
        lat: (28.6139 + idx * 0.0001).toFixed(5),
        lon: (77.2090 + idx * 0.00015).toFixed(5),
        alt: (120.0 + Math.sin(idx * 0.2) * 1.5).toFixed(1),
        speed: "8.0",
        yaw: "014.0",
        pitch: "-30.0",
        blur: (285 + (idx * 13) % 95).toFixed(1),
        bh: (0.14 + (idx * 0.015) % 0.06).toFixed(2),
        covisibility: 78,
      }));

  const activeWp = keyframes[selectedKeyframeIndex] || keyframes[0];

  return (
    <div className="w-80 h-full border-r border-cyan-500/20 bg-slate-950/95 backdrop-blur-md flex flex-col text-white font-mono select-none">
      {/* Panel Header */}
      <div className="p-3 border-b border-cyan-500/20 flex items-center justify-between bg-slate-900/50">
        <span className="text-xs font-bold text-cyan-400 tracking-wider flex items-center gap-1.5">
          <Navigation className="w-4 h-4 text-cyan-400" />
          TELEMETRY & FLIGHT TRACK
        </span>
        <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-emerald-500/40 text-emerald-400 bg-emerald-950/30">
          RTK FIX (1.2cm)
        </Badge>
      </div>

      {/* Flight Attitude & Avionics Gauges */}
      <div className="p-3 border-b border-slate-800/80 bg-slate-900/30 space-y-2.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400 flex items-center gap-1">
            <Gauge className="w-3.5 h-3.5 text-cyan-400" />
            AVIONICS HUD
          </span>
          <span className="text-[10px] text-slate-500">MISB 0601 / KLV</span>
        </div>

        {/* 4-Box Telemetry Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-slate-900/80 border border-slate-800 rounded p-2 flex flex-col">
            <span className="text-[10px] text-slate-500">ALTITUDE AGL</span>
            <span className="text-base font-bold text-cyan-300">
              {activeWp.alt} <span className="text-xs font-normal text-slate-400">m</span>
            </span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded p-2 flex flex-col">
            <span className="text-[10px] text-slate-500">GROUND SPEED</span>
            <span className="text-base font-bold text-emerald-400">
              {activeWp.speed} <span className="text-xs font-normal text-slate-400">m/s</span>
            </span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded p-2 flex flex-col">
            <span className="text-[10px] text-slate-500">HEADING (YAW)</span>
            <span className="text-base font-bold text-amber-300">
              {activeWp.yaw}°
            </span>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded p-2 flex flex-col">
            <span className="text-[10px] text-slate-500">GIMBAL PITCH</span>
            <span className="text-base font-bold text-slate-200">
              {activeWp.pitch}°
            </span>
          </div>
        </div>

        {/* GPS Constellation Bar */}
        <div className="flex items-center justify-between text-[11px] text-slate-400 px-1 pt-1">
          <span className="flex items-center gap-1">
            <Radio className="w-3 h-3 text-emerald-400" />
            26 SATELLITES (L1/L2)
          </span>
          <span className="text-slate-300">PDOP: 1.12</span>
        </div>
      </div>

      {/* 2D Overhead Flight Path Minimap Canvas */}
      <div className="p-3 border-b border-slate-800/80">
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="text-slate-400 flex items-center gap-1">
            <Compass className="w-3.5 h-3.5 text-cyan-400" />
            2D MISSION CORRIDOR
          </span>
          <span className="text-[10px] text-slate-500">UTM GRID 10m</span>
        </div>

        <div className="relative w-full h-36 bg-[#04060a] border border-cyan-500/20 rounded-lg overflow-hidden flex items-center justify-center">
          {/* Subtle Grid Lines */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#08334415_1px,transparent_1px),linear-gradient(to_bottom,#08334415_1px,transparent_1px)] bg-[size:16px_16px]" />

          {/* SVG Flight Spline */}
          <svg className="w-full h-full p-3" viewBox="0 0 280 120">
            {/* Flight Path Corridor / Buffer */}
            <path
              d="M 20 80 Q 80 40, 140 60 T 260 30"
              fill="none"
              stroke="#06b6d4"
              strokeWidth="12"
              strokeOpacity="0.12"
              strokeLinecap="round"
            />
            {/* Flight Spline */}
            <path
              d="M 20 80 Q 80 40, 140 60 T 260 30"
              fill="none"
              stroke="#06b6d4"
              strokeWidth="2"
              strokeDasharray="4 2"
            />
            {/* Keyframe nodes */}
            {keyframes.map((_, i) => {
              const t = i / (keyframes.length - 1);
              const x = 20 + t * 240;
              const y = 80 - t * 45 + Math.sin(t * Math.PI * 2) * 12;
              const isSelected = selectedKeyframeIndex === i;

              return (
                <g key={i} className="cursor-pointer" onClick={() => setSelectedKeyframeIndex(i)}>
                  <circle
                    cx={x}
                    cy={y}
                    r={isSelected ? 6 : 3.5}
                    fill={isSelected ? '#22d3ee' : '#0891b2'}
                    stroke={isSelected ? '#ffffff' : '#0e7490'}
                    strokeWidth={isSelected ? 2 : 1}
                  />
                  {isSelected && (
                    <circle
                      cx={x}
                      cy={y}
                      r={10}
                      fill="none"
                      stroke="#22d3ee"
                      strokeWidth="1"
                      className="animate-ping origin-center"
                    />
                  )}
                </g>
              );
            })}
          </svg>

          {/* Top-right North indicator */}
          <div className="absolute top-2 right-2 text-[10px] text-cyan-400 font-bold bg-slate-900/80 px-1 rounded border border-cyan-500/20">
            ▲ N
          </div>
        </div>
      </div>

      {/* Keyframe Quality Gating Strip */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="p-3 border-b border-slate-800/80 flex items-center justify-between text-xs">
          <span className="text-slate-400 flex items-center gap-1">
            <Camera className="w-3.5 h-3.5 text-cyan-400" />
            GATE-PASSED KEYFRAMES ({keyframes.length})
          </span>
          <span className="text-[10px] text-cyan-400">b/H ∈ [0.10, 0.25]</span>
        </div>

        <ScrollArea className="flex-1 px-3 py-2">
          <div className="space-y-1.5">
            {keyframes.map((kf, idx) => {
              const isSelected = selectedKeyframeIndex === idx;
              return (
                <div
                  key={kf.id}
                  onClick={() => setSelectedKeyframeIndex(idx)}
                  className={`p-2 rounded border transition-all cursor-pointer text-xs ${
                    isSelected
                      ? 'bg-cyan-950/40 border-cyan-500/50 shadow-sm shadow-cyan-900/40'
                      : 'bg-slate-900/40 border-slate-800/60 hover:bg-slate-900 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`font-semibold ${isSelected ? 'text-cyan-300' : 'text-slate-200'}`}>
                      {kf.id}
                    </span>
                    <span className="text-[10px] text-slate-500">{kf.time}s</span>
                  </div>

                  <div className="grid grid-cols-3 gap-1 mt-1 text-[10px] text-slate-400">
                    <div>
                      <span className="text-slate-600 block">BLUR σ²</span>
                      <span className="text-emerald-400">{kf.blur}</span>
                    </div>
                    <div>
                      <span className="text-slate-600 block">b/H RATIO</span>
                      <span className="text-cyan-300">{kf.bh}</span>
                    </div>
                    <div>
                      <span className="text-slate-600 block">COVIS.</span>
                      <span className="text-slate-300">{kf.covisibility}%</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
};
