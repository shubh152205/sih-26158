"use client";

import React, { useEffect, useState } from 'react';
import { useMissionStore } from '@/lib/useMissionStore';
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
import { Textarea } from '@/components/ui/textarea';
import { 
  Edit3, 
  Shield, 
  MapPin, 
  Radio, 
  Cpu, 
  FileText, 
  Save, 
  CheckCircle2 
} from 'lucide-react';
import { toast } from 'sonner';

export const EditProjectModal: React.FC = () => {
  const { 
    isEditProjectModalOpen, 
    setIsEditProjectModalOpen, 
    activeJob, 
    projectMetadata, 
    updateProjectMetadata 
  } = useMissionStore();

  const jobId = activeJob?.job_id || 'test-new-video';
  const currentMeta = projectMetadata[jobId] || {
    projectName: activeJob?.mission_name || `Mission ${jobId}`,
    targetLocation: 'Designated AOI',
    operatorCallsign: 'COMMAND-1',
    sensorModel: 'Zenmuse P1 35mm',
    reconProfile: 'Watertight Metric Mesh',
    tacticalNotes: 'Tactical aerial reconnaissance data.',
  };

  const [projectName, setProjectName] = useState(currentMeta.projectName);
  const [targetLocation, setTargetLocation] = useState(currentMeta.targetLocation);
  const [operatorCallsign, setOperatorCallsign] = useState(currentMeta.operatorCallsign);
  const [sensorModel, setSensorModel] = useState(currentMeta.sensorModel);
  const [tacticalNotes, setTacticalNotes] = useState(currentMeta.tacticalNotes);

  useEffect(() => {
    if (activeJob) {
      const meta = projectMetadata[activeJob.job_id] || {
        projectName: activeJob.mission_name || `Mission ${activeJob.job_id}`,
        targetLocation: 'Designated AOI',
        operatorCallsign: 'COMMAND-1',
        sensorModel: 'Zenmuse P1 35mm',
        reconProfile: 'Watertight Metric Mesh',
        tacticalNotes: '',
      };
      setProjectName(meta.projectName);
      setTargetLocation(meta.targetLocation);
      setOperatorCallsign(meta.operatorCallsign);
      setSensorModel(meta.sensorModel);
      setTacticalNotes(meta.tacticalNotes);
    }
  }, [activeJob, projectMetadata, isEditProjectModalOpen]);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeJob) return;

    updateProjectMetadata(activeJob.job_id, {
      projectName,
      targetLocation,
      operatorCallsign,
      sensorModel,
      tacticalNotes,
    });

    toast.success(`Project "${projectName}" updated successfully!`);
    setIsEditProjectModalOpen(false);
  };

  return (
    <Dialog open={isEditProjectModalOpen} onOpenChange={setIsEditProjectModalOpen}>
      <DialogContent className="bg-slate-950 border border-cyan-500/40 text-white font-mono max-w-lg shadow-2xl shadow-black/90 p-6">
        <DialogHeader>
          <DialogTitle className="text-cyan-400 text-base flex items-center gap-2">
            <Edit3 className="w-5 h-5 text-cyan-400" />
            EDIT PROJECT SPECIFICATIONS
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Modify project identification, operator details, target location, and tactical mission parameters.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSave} className="space-y-4 text-xs mt-2">
          <div className="space-y-1">
            <Label className="text-slate-300 font-semibold flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-cyan-400" />
              PROJECT TITLE *
            </Label>
            <Input
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              required
              className="bg-slate-900 border-slate-700 text-cyan-300 text-xs h-8 focus:border-cyan-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-slate-300 font-semibold flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                TARGET LOCATION / AOI
              </Label>
              <Input
                value={targetLocation}
                onChange={(e) => setTargetLocation(e.target.value)}
                className="bg-slate-900 border-slate-700 text-slate-200 text-xs h-8 focus:border-cyan-500"
              />
            </div>

            <div className="space-y-1">
              <Label className="text-slate-300 font-semibold flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-cyan-400" />
                OPERATOR CALLSIGN
              </Label>
              <Input
                value={operatorCallsign}
                onChange={(e) => setOperatorCallsign(e.target.value)}
                className="bg-slate-900 border-slate-700 text-slate-200 text-xs h-8 focus:border-cyan-500"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-slate-300 font-semibold flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              UAV SENSOR PLATFORM
            </Label>
            <select
              value={sensorModel}
              onChange={(e) => setSensorModel(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 text-xs text-slate-200 h-8 focus:border-cyan-500 focus:outline-none"
            >
              <option value="Zenmuse P1 35mm">DJI Matrice 300 RTK (Zenmuse P1 35mm)</option>
              <option value="Mavic 3E Mechanical">DJI Mavic 3 Enterprise (Mechanical)</option>
              <option value="Skydio Autonomous 4K">Skydio X2 Autonomous 4K</option>
              <option value="Generic MISB UAV">Custom Tactical Drone (MISB 0601)</option>
            </select>
          </div>

          <div className="space-y-1">
            <Label className="text-slate-300 font-semibold flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-cyan-400" />
              TACTICAL INTEL NOTES & OBJECTIVES
            </Label>
            <Textarea
              value={tacticalNotes}
              onChange={(e) => setTacticalNotes(e.target.value)}
              rows={3}
              placeholder="Enter operational notes, designated ingress corridors, or priority structural elements..."
              className="bg-slate-900 border-slate-700 text-slate-200 text-xs focus:border-cyan-500 resize-none"
            />
          </div>

          <DialogFooter className="pt-2 flex items-center justify-between border-t border-slate-800">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsEditProjectModalOpen(false)}
              className="h-8 border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="h-8 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold px-4"
            >
              <Save className="w-3.5 h-3.5 mr-1.5" />
              SAVE PROJECT DETAILS
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
