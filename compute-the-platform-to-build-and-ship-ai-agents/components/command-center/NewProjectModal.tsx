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
  FolderPlus, 
  Video, 
  FileCode, 
  CheckCircle2, 
  RefreshCw, 
  Cpu, 
  Zap, 
  MapPin, 
  Shield, 
  Radio
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';

export const NewProjectModal: React.FC = () => {
  const { 
    isNewProjectModalOpen, 
    setIsNewProjectModalOpen, 
    setActiveJob, 
    updateProjectMetadata 
  } = useMissionStore();

  const [mode, setMode] = useState<'upload' | 'synthetic'>('upload');
  const [projectName, setProjectName] = useState('Border Sector 4 Recon');
  const [targetLocation, setTargetLocation] = useState('North Outpost AOI');
  const [operatorCallsign, setOperatorCallsign] = useState('EAGLE-1');
  const [droneModel, setDroneModel] = useState('dji_m300_rtk');
  const [reconProfile, setReconProfile] = useState('Watertight High-Res Mesh');
  const [tacticalNotes, setTacticalNotes] = useState('Priority 1 forward reconnaissance pass.');

  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [telemetryFile, setTelemetryFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === 'upload' && !videoFile) {
      toast.error("Please attach a drone video (.mp4 or .mov)");
      return;
    }

    setIsProcessing(true);
    toast.info(`Initializing new project: "${projectName}"...`);

    try {
      let jobSummary;
      if (mode === 'upload' && videoFile) {
        jobSummary = await apiClient.uploadMissionVideo(videoFile, telemetryFile || undefined, projectName);
      } else {
        jobSummary = await apiClient.runDemoRecon();
      }

      // Save user-defined metadata
      updateProjectMetadata(jobSummary.job_id, {
        projectName,
        targetLocation,
        operatorCallsign,
        sensorModel: droneModel,
        reconProfile,
        tacticalNotes,
      });

      toast.success(`Project "${projectName}" launched successfully (ID: ${jobSummary.job_id})`);
      setIsNewProjectModalOpen(false);

      // Refresh job status
      const updated = await apiClient.getJobStatus(jobSummary.job_id);
      setActiveJob(updated);
    } catch (err: any) {
      console.error(err);
      toast.error(err.message || "Failed to initialize new project");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <Dialog open={isNewProjectModalOpen} onOpenChange={setIsNewProjectModalOpen}>
      <DialogContent className="bg-slate-950 border border-cyan-500/40 text-white font-mono max-w-xl shadow-2xl shadow-black/90 p-6">
        <DialogHeader>
          <DialogTitle className="text-cyan-400 text-base flex items-center gap-2">
            <FolderPlus className="w-5 h-5 text-cyan-400" />
            START NEW 3D RECONSTRUCTION PROJECT
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Ingest monocular UAV single-pass video or run instant tactical reconnaissance to generate georeferenced 3D models.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs mt-2">
          {/* Project Details */}
          <div className="grid grid-cols-2 gap-3 p-3 bg-slate-900/50 border border-slate-800 rounded-lg">
            <div className="space-y-1">
              <Label className="text-slate-300 font-semibold flex items-center gap-1">
                <Shield className="w-3.5 h-3.5 text-cyan-400" />
                PROJECT TITLE *
              </Label>
              <Input
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                required
                placeholder="e.g. Sector 4 Forward Recon"
                className="bg-slate-950 border-slate-700 text-cyan-300 text-xs h-8"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-slate-300 font-semibold flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                TARGET LOCATION / AOI
              </Label>
              <Input
                value={targetLocation}
                onChange={(e) => setTargetLocation(e.target.value)}
                placeholder="e.g. North Ridge Complex"
                className="bg-slate-950 border-slate-700 text-slate-200 text-xs h-8"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-slate-300 font-semibold flex items-center gap-1">
                <Radio className="w-3.5 h-3.5 text-cyan-400" />
                OPERATOR CALLSIGN
              </Label>
              <Input
                value={operatorCallsign}
                onChange={(e) => setOperatorCallsign(e.target.value)}
                placeholder="e.g. HAWK-1"
                className="bg-slate-950 border-slate-700 text-slate-200 text-xs h-8"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-slate-300 font-semibold flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                UAV PLATFORM SENSOR
              </Label>
              <select
                value={droneModel}
                onChange={(e) => setDroneModel(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded px-2 text-xs text-slate-200 h-8 focus:border-cyan-500 focus:outline-none"
              >
                <option value="dji_m300_rtk">DJI Matrice 300 RTK (P1 35mm)</option>
                <option value="dji_mavic_3e">DJI Mavic 3 Enterprise (4/3 CMOS)</option>
                <option value="skydio_x2">Skydio X2 Autonomous 4K</option>
                <option value="custom_uav">Custom Tactical Drone (MISB 0601)</option>
              </select>
            </div>
          </div>

          {/* Mode Selector Tabs */}
          <Tabs value={mode} onValueChange={(v) => setMode(v as 'upload' | 'synthetic')} className="w-full">
            <TabsList className="grid grid-cols-2 bg-slate-900 border border-slate-800 text-xs">
              <TabsTrigger value="upload" className="data-[state=active]:bg-cyan-600/30 data-[state=active]:text-cyan-300">
                <Video className="w-3.5 h-3.5 mr-1.5 text-cyan-400" />
                UPLOAD DRONE ASSETS
              </TabsTrigger>
              <TabsTrigger value="synthetic" className="data-[state=active]:bg-cyan-600/30 data-[state=active]:text-cyan-300">
                <Zap className="w-3.5 h-3.5 mr-1.5 text-emerald-400" />
                INSTANT DEMO RECON
              </TabsTrigger>
            </TabsList>

            {/* Tab 1: Upload Assets */}
            <TabsContent value="upload" className="space-y-3 pt-2">
              <div className="space-y-1">
                <Label className="text-slate-300 font-semibold flex items-center gap-1.5">
                  <Video className="w-4 h-4 text-cyan-400" />
                  DRONE FLIGHT VIDEO (.MP4, .MOV, .MKV) *
                </Label>
                <div className="relative border-2 border-dashed border-slate-800 hover:border-cyan-500/50 rounded-lg p-3 text-center transition-colors bg-slate-900/40">
                  <input
                    type="file"
                    accept="video/mp4,video/quicktime,video/x-matroska"
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
                      <span>Click or drag UAV video file here (4K/1080p, 30/60 FPS)</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-slate-300 font-semibold flex items-center gap-1.5">
                  <FileCode className="w-4 h-4 text-cyan-400" />
                  TELEMETRY LOG (.SRT, .CSV, .KLV) [OPTIONAL]
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
                      <span>Subtitles (.srt) or flight log for 1:1 metric WGS84 UTM georeferencing</span>
                    )}
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* Tab 2: Synthetic Demo */}
            <TabsContent value="synthetic" className="p-3 bg-slate-900/40 border border-slate-800 rounded-lg space-y-2 text-slate-300">
              <p className="text-[11px] leading-relaxed">
                Immediately launch a single-pass tactical corridor reconnaissance pass. The pipeline will automatically generate synchronized flight telemetry, extract laplacian keyframes, solve Kabsch relative poses, lock Umeyama metric scale, and extract a watertight 3D mesh.
              </p>
              <div className="text-[10px] text-cyan-300 bg-cyan-950/40 border border-cyan-500/30 p-2 rounded">
                ⚡ Ideal for instant jury demonstrations, test evaluation, and benchmark validation.
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter className="pt-2 flex items-center justify-between border-t border-slate-800">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsNewProjectModalOpen(false)}
              className="h-8 border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isProcessing}
              className="h-8 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold px-4 shadow-lg shadow-cyan-950/50"
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  INITIALIZING PROJECT...
                </>
              ) : (
                <>
                  <FolderPlus className="w-3.5 h-3.5 mr-1.5" />
                  CREATE & LAUNCH PROJECT
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
