"use client";

import React, { useState } from 'react';
import { useMissionStore } from '@/lib/useMissionStore';
import { apiClient } from '@/lib/apiClient';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { 
  UploadCloud, 
  Video, 
  FileCode, 
  CheckCircle2, 
  RefreshCw, 
  Sliders, 
  Cpu 
} from 'lucide-react';
import { toast } from 'sonner';

export const MissionUploadModal: React.FC = () => {
  const { isUploadModalOpen, setIsUploadModalOpen, setActiveJob } = useMissionStore();
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [telemetryFile, setTelemetryFile] = useState<File | null>(null);
  const [droneModel, setDroneModel] = useState('dji_m300_rtk');
  const [isUploading, setIsUploading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!videoFile) {
      toast.error("Please provide a drone video file (.mp4 or .mov)");
      return;
    }

    setIsUploading(true);
    toast.info("Uploading mission assets and initializing compute pipeline...");

    try {
      const res = await apiClient.uploadMissionVideo(videoFile, telemetryFile || undefined, droneModel);
      toast.success(`Job started: ${res.job_id}`);
      setIsUploadModalOpen(false);

      const job = await apiClient.getJobStatus(res.job_id);
      setActiveJob(job);
    } catch (err: any) {
      console.error(err);
      toast.error(err.message || "Failed to launch reconstruction mission");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={isUploadModalOpen} onOpenChange={setIsUploadModalOpen}>
      <DialogContent className="bg-slate-950 border border-cyan-500/30 text-white font-mono max-w-lg shadow-2xl shadow-black/80">
        <DialogHeader>
          <DialogTitle className="text-cyan-400 text-base flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-cyan-400" />
            NEW 3D RECON MISSION INGESTION
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Ingest raw single-pass UAV video and synchronous telemetry for photogrammetric reconstruction.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs mt-2">
          {/* Video file input */}
          <div className="space-y-1.5">
            <Label className="text-slate-300 flex items-center gap-1.5 font-semibold">
              <Video className="w-4 h-4 text-cyan-400" />
              DRONE FLIGHT VIDEO (.MP4, .MOV) *
            </Label>
            <div className="relative border-2 border-dashed border-slate-800 hover:border-cyan-500/50 rounded-lg p-3 text-center transition-colors bg-slate-900/40">
              <input
                type="file"
                accept="video/mp4,video/quicktime"
                onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              <div className="text-slate-400">
                {videoFile ? (
                  <span className="text-cyan-300 font-semibold flex items-center justify-center gap-1">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    {videoFile.name} ({(videoFile.size / (1024 * 1024)).toFixed(1)} MB)
                  </span>
                ) : (
                  <span>Click or drag drone video file here</span>
                )}
              </div>
            </div>
          </div>

          {/* Telemetry file input */}
          <div className="space-y-1.5">
            <Label className="text-slate-300 flex items-center gap-1.5 font-semibold">
              <FileCode className="w-4 h-4 text-cyan-400" />
              TELEMETRY LOG (.SRT, .KLV, .CSV) [OPTIONAL]
            </Label>
            <div className="relative border border-slate-800 hover:border-cyan-500/50 rounded-lg p-2.5 text-center transition-colors bg-slate-900/40">
              <input
                type="file"
                accept=".srt,.csv,.klv,.txt"
                onChange={(e) => setTelemetryFile(e.target.files?.[0] || null)}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              <div className="text-slate-400 text-[11px]">
                {telemetryFile ? (
                  <span className="text-cyan-300 font-semibold flex items-center justify-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    {telemetryFile.name}
                  </span>
                ) : (
                  <span>Subtitles (.srt) or MISB 0601 KLV metadata stream</span>
                )}
              </div>
            </div>
          </div>

          {/* Drone Platform Preset */}
          <div className="space-y-1.5">
            <Label className="text-slate-300 flex items-center gap-1.5 font-semibold">
              <Cpu className="w-4 h-4 text-cyan-400" />
              UAV PLATFORM & SENSOR PROFILE
            </Label>
            <select
              value={droneModel}
              onChange={(e) => setDroneModel(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="dji_m300_rtk">DJI Matrice 300 RTK (Zenmuse P1 35mm)</option>
              <option value="dji_mavic_3e">DJI Mavic 3 Enterprise (Mechanical Shutter)</option>
              <option value="skydio_x2">Skydio X2 Autonomous 4K</option>
              <option value="custom_uav">Custom Tactical Drone (Generic Perspective)</option>
            </select>
          </div>

          {/* Feature Checkboxes */}
          <div className="p-3 bg-slate-900/70 border border-slate-800 rounded space-y-1.5 text-[11px]">
            <div className="flex items-center gap-2 text-slate-300">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Lorensen Marching Cubes Watertight SDF Enclosure</span>
            </div>
            <div className="flex items-center gap-2 text-slate-300">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Umeyama Sim(3) DOP-Weighted Georeferencing</span>
            </div>
            <div className="flex items-center gap-2 text-slate-300">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Multi-Ray Anti-Hallucination Confidence Gating</span>
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsUploadModalOpen(false)}
              className="border-slate-800 text-slate-400 hover:text-white"
            >
              CANCEL
            </Button>
            <Button
              type="submit"
              disabled={isUploading}
              className="bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold px-4"
            >
              {isUploading ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  PROCESSING...
                </>
              ) : (
                'LAUNCH RECON PIPELINE'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
