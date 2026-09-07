"use client";

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import { useMissionStore, RenderLayer } from '@/lib/useMissionStore';
import { useToolStore } from '@/lib/useToolStore';
import { 
  Layers, 
  Ruler, 
  ShieldCheck, 
  Eye, 
  Compass, 
  Maximize2, 
  Crosshair, 
  Grid,
  CheckCircle2,
  AlertTriangle,
  RotateCcw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// Dynamically import ThreeMeshViewer with SSR disabled
const ThreeMeshViewer = dynamic(
  () => import('./ThreeMeshViewer').then((mod) => mod.ThreeMeshViewer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex flex-col items-center justify-center bg-[#07090e] text-slate-400 gap-3">
        <div className="w-10 h-10 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-mono tracking-wider text-cyan-400">INITIALIZING TACTICAL 3D VIEWPORT...</span>
      </div>
    ),
  }
);

interface ViewportContainerProps {
  modelUrl?: string;
}

export const ViewportContainer: React.FC<ViewportContainerProps> = ({ modelUrl }) => {
  const { activeLayer, setActiveLayer, hoveredCoordinate, telemetryTrack } = useMissionStore();
  const { activeTool, setActiveTool, pickedPoints, clearPoints } = useToolStore();
  const [showHud, setShowHud] = useState(true);

  const layers: { id: RenderLayer; label: string; icon: any }[] = [
    { id: 'mesh', label: 'Textured PBR', icon: Layers },
    { id: 'wireframe', label: 'Wireframe', icon: Grid },
    { id: 'confidence', label: 'Audit / Confidence', icon: ShieldCheck },
    { id: 'dsm', label: 'Elevation Gradient', icon: Eye },
    { id: 'pointcloud', label: 'Point Cloud', icon: Crosshair },
  ];

  return (
    <div className="relative w-full h-full bg-[#07090e] overflow-hidden select-none">
      {/* Primary 3D WebGL Canvas */}
      <ThreeMeshViewer modelUrl={modelUrl} />

      {/* Top Floating Layer Switcher */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-1.5 p-1 bg-slate-950/80 backdrop-blur-md border border-cyan-500/20 rounded-lg shadow-xl shadow-black/50">
        {layers.map((layer) => {
          const Icon = layer.icon;
          const isActive = activeLayer === layer.id;
          return (
            <button
              key={layer.id}
              onClick={() => setActiveLayer(layer.id)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-mono transition-all ${
                isActive
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/20 font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
              <span>{layer.label}</span>
            </button>
          );
        })}
      </div>

      {/* Top Right Quick Controls */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowHud(!showHud)}
          className="h-8 px-2.5 bg-slate-950/80 backdrop-blur-md border-cyan-500/20 text-slate-300 text-xs font-mono hover:bg-slate-900 hover:text-cyan-300"
        >
          <Compass className="w-3.5 h-3.5 mr-1 text-cyan-400" />
          {showHud ? 'Hide HUD' : 'Show HUD'}
        </Button>
      </div>

      {/* Active Tactical Tool Floating Banner */}
      {activeTool !== 'none' && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3 px-4 py-2 bg-slate-950/90 backdrop-blur-md border border-amber-500/40 rounded-full shadow-lg shadow-black/60 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-amber-400 font-semibold">
            <Ruler className="w-4 h-4 animate-pulse" />
            <span className="uppercase">ACTIVE MODE: {activeTool}</span>
          </div>
          <span className="text-slate-400">
            {pickedPoints.length === 0
              ? 'Click terrain in 3D to set Point A'
              : pickedPoints.length === 1
              ? 'Click terrain in 3D to set Point B'
              : `${pickedPoints.length} points set`}
          </span>
          <button
            onClick={clearPoints}
            className="flex items-center gap-1 px-2 py-0.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded text-[11px] transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            Reset
          </button>
          <button
            onClick={() => setActiveTool('none')}
            className="text-slate-500 hover:text-rose-400 transition-colors ml-1 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Real-Time Geodetic Coordinates & Crosshair HUD */}
      {showHud && (
        <div className="absolute bottom-4 left-4 z-20 flex flex-col gap-2 p-3 bg-slate-950/85 backdrop-blur-md border border-cyan-500/20 rounded-lg shadow-xl shadow-black/50 text-[11px] font-mono text-slate-300 min-w-[280px]">
          <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
            <span className="text-cyan-400 font-semibold tracking-wider flex items-center gap-1.5">
              <Crosshair className="w-3.5 h-3.5" />
              GEOSPATIAL ANCHOR
            </span>
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-cyan-500/30 text-cyan-300 bg-cyan-950/40">
              WGS84 / UTM 43N
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            <div className="flex justify-between">
              <span className="text-slate-500">EASTING:</span>
              <span className="text-slate-200">
                {hoveredCoordinate ? `${hoveredCoordinate.x.toFixed(2)} m` : '243,180.40 m'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">NORTHING:</span>
              <span className="text-slate-200">
                {hoveredCoordinate ? `${hoveredCoordinate.z.toFixed(2)} m` : '2,154,200.15 m'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">ELEVATION (Z):</span>
              <span className="text-emerald-400 font-semibold">
                {hoveredCoordinate ? `${hoveredCoordinate.y.toFixed(2)} m` : '42.80 m AGL'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">CONFIDENCE:</span>
              <span className="text-cyan-300">0.965 (High)</span>
            </div>
          </div>

          <div className="flex items-center justify-between pt-1 border-t border-slate-800/80 text-[10px] text-slate-400">
            <div className="flex items-center gap-1 text-emerald-400">
              <CheckCircle2 className="w-3 h-3" />
              <span>WATERTIGHT MANIFOLD (2-SURFACE)</span>
            </div>
            <span className="text-slate-500">SCALE 1:1 METRIC</span>
          </div>
        </div>
      )}

      {/* Bottom Right Floating Measurement Quick-Launcher */}
      <div className="absolute bottom-4 right-4 z-20 flex items-center gap-1.5 p-1 bg-slate-950/85 backdrop-blur-md border border-cyan-500/20 rounded-lg shadow-xl shadow-black/50">
        <Button
          size="sm"
          variant={activeTool === 'distance' ? 'default' : 'ghost'}
          onClick={() => setActiveTool(activeTool === 'distance' ? 'none' : 'distance')}
          className={`h-8 px-2.5 text-xs font-mono ${
            activeTool === 'distance'
              ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400 font-semibold'
              : 'text-slate-300 hover:text-cyan-300 hover:bg-slate-900'
          }`}
          title="Distance Ruler"
        >
          <Ruler className="w-3.5 h-3.5 mr-1" />
          Ruler
        </Button>
        <Button
          size="sm"
          variant={activeTool === 'area' ? 'default' : 'ghost'}
          onClick={() => setActiveTool(activeTool === 'area' ? 'none' : 'area')}
          className={`h-8 px-2.5 text-xs font-mono ${
            activeTool === 'area'
              ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400 font-semibold'
              : 'text-slate-300 hover:text-cyan-300 hover:bg-slate-900'
          }`}
          title="Area Measurement"
        >
          <Maximize2 className="w-3.5 h-3.5 mr-1" />
          Area
        </Button>
        <Button
          size="sm"
          variant={activeTool === 'los' ? 'default' : 'ghost'}
          onClick={() => setActiveTool(activeTool === 'los' ? 'none' : 'los')}
          className={`h-8 px-2.5 text-xs font-mono ${
            activeTool === 'los'
              ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400 font-semibold'
              : 'text-slate-300 hover:text-cyan-300 hover:bg-slate-900'
          }`}
          title="Line-of-Sight Analysis"
        >
          <Crosshair className="w-3.5 h-3.5 mr-1" />
          LoS Raycast
        </Button>
      </div>
    </div>
  );
};
