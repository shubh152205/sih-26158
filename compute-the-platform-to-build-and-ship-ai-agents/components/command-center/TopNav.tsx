"use client";

import React, { useState } from 'react';
import { useMissionStore } from '@/lib/useMissionStore';
import { apiClient } from '@/lib/apiClient';
import { 
  Shield, 
  Play, 
  UploadCloud, 
  Cpu, 
  Wifi, 
  RefreshCw, 
  Layers, 
  CheckCircle, 
  Zap,
  Globe,
  Radio
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

interface TopNavProps {
  onTogglePlatformView?: () => void;
  isPlatformView?: boolean;
}

export const TopNav: React.FC<TopNavProps> = ({ onTogglePlatformView, isPlatformView = false }) => {
  const { 
    activeJob, 
    setActiveJob, 
    jobs, 
    setTelemetryTrack, 
    setIsUploadModalOpen, 
    hardware 
  } = useMissionStore();
  const [isRunningDemo, setIsRunningDemo] = useState(false);

  const handleRunDemo = async () => {
    setIsRunningDemo(true);
    toast.info("Initiating single-pass reconnaissance pipeline...");
    try {
      const res = await apiClient.runDemoRecon();
      toast.success(`Pipeline launched: ${res.job_id}`);
      // Query job status
      const job = await apiClient.getJobStatus(res.job_id);
      setActiveJob(job);
    } catch (err: any) {
      console.error(err);
      toast.error(err.message || "Failed to trigger synthetic recon");
    } finally {
      setIsRunningDemo(false);
    }
  };

  return (
    <header className="h-14 border-b border-cyan-500/20 bg-slate-950/90 backdrop-blur-md px-4 flex items-center justify-between text-white font-mono text-xs z-30 select-none">
      {/* Left: Brand / System Identifier */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-2.5 py-1 bg-cyan-950/40 border border-cyan-500/30 rounded-md">
          <Shield className="w-4 h-4 text-cyan-400" />
          <span className="font-bold tracking-wider text-slate-100 text-sm">
            NTRO <span className="text-cyan-400">SIH26158</span>
          </span>
          <span className="text-[10px] text-cyan-300/70 border-l border-cyan-500/30 pl-2">
            TACTICAL 3D RECON
          </span>
        </div>

        {/* Mission Dropdown Selector */}
        <div className="flex items-center gap-2 px-2.5 py-1 bg-slate-900/90 border border-cyan-500/30 rounded-md">
          <span className="text-cyan-400 text-[11px] font-bold">MISSION:</span>
          <select
            value={activeJob?.job_id || ''}
            onChange={async (e) => {
              const selected = jobs.find((j) => j.job_id === e.target.value);
              if (selected) {
                setActiveJob(selected);
                try {
                  const track = await apiClient.getTelemetryTrack(selected.job_id);
                  setTelemetryTrack(track);
                } catch (err) {
                  console.warn("Failed to load telemetry track:", err);
                }
                toast.success(`Active Mission: ${selected.job_id}`);
              }
            }}
            className="bg-slate-950 text-cyan-300 font-semibold text-xs border border-slate-700 rounded px-2 py-0.5 focus:outline-none focus:border-cyan-500 cursor-pointer max-w-[220px] truncate"
          >
            {jobs.length > 0 ? (
              jobs.map((j) => (
                <option key={j.job_id} value={j.job_id} className="bg-slate-950 text-slate-200">
                  {j.job_id} • {j.mission_name} ({j.keyframe_count || 47} KFs)
                </option>
              ))
            ) : (
              <option value="test-new-video" className="bg-slate-950 text-slate-200">
                test-new-video • Tactical Drone Recon (47 KFs)
              </option>
            )}
          </select>
          <Badge className="bg-emerald-950 text-emerald-400 border border-emerald-500/30 text-[10px] px-1.5 py-0">
            WATERTIGHT
          </Badge>
        </div>
      </div>

      {/* Middle: Actions */}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          onClick={handleRunDemo}
          disabled={isRunningDemo}
          className="h-8 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold px-3 shadow-lg shadow-cyan-900/30 transition-all"
        >
          {isRunningDemo ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              EXECUTING PIPELINE...
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
              RUN RECON PIPELINE
            </>
          )}
        </Button>

        <Button
          size="sm"
          variant="outline"
          onClick={() => setIsUploadModalOpen(true)}
          className="h-8 border-cyan-500/30 bg-slate-900/60 text-slate-200 hover:bg-slate-800 hover:text-cyan-300 px-3"
        >
          <UploadCloud className="w-3.5 h-3.5 mr-1.5 text-cyan-400" />
          UPLOAD MISSION DATA
        </Button>

        {onTogglePlatformView && (
          <Button
            size="sm"
            variant="ghost"
            onClick={onTogglePlatformView}
            className="h-8 text-slate-400 hover:text-slate-100 hover:bg-slate-800 text-[11px]"
          >
            <Globe className="w-3.5 h-3.5 mr-1 text-slate-400" />
            {isPlatformView ? "VIEW 3D COMMAND" : "LANDING PAGE"}
          </Button>
        )}
      </div>

      {/* Right: Hardware & Telemetry Badges */}
      <div className="hidden md:flex items-center gap-2.5">
        {/* Hardware / GPU */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900/60 border border-slate-800/80 rounded text-[11px] text-slate-400">
          <Cpu className="w-3.5 h-3.5 text-emerald-400" />
          <span>GPU:</span>
          <span className="text-slate-200 font-semibold">
            {hardware ? hardware.device : 'RTX 4090 Sim'}
          </span>
          <span className="text-emerald-400 ml-1">
            {hardware ? `${(hardware.gpu_vram_used_gb || 0).toFixed(1)}GB` : '2.1GB'}
          </span>
        </div>

        {/* Real-time Link */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900/60 border border-slate-800/80 rounded text-[11px] text-slate-400">
          <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span className="text-slate-300">TELEMETRY LINK:</span>
          <span className="text-emerald-400 font-semibold">ONLINE</span>
        </div>

        {/* Air-Gapped Local Indicator */}
        <div className="flex items-center gap-1 px-2 py-1 bg-emerald-950/30 border border-emerald-500/20 rounded text-[10px] text-emerald-400">
          <CheckCircle className="w-3 h-3" />
          <span>AIR-GAPPED</span>
        </div>
      </div>
    </header>
  );
};
