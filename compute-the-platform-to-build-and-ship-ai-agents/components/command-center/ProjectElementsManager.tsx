"use client";

import React, { useState } from 'react';
import { useMissionStore, TacticalElementType, TacticalElement } from '@/lib/useMissionStore';
import { useToolStore } from '@/lib/useToolStore';
import { 
  FolderEdit, 
  MapPin, 
  Plus, 
  Crosshair, 
  Eye, 
  Trash2, 
  Edit2, 
  Layers, 
  Sliders, 
  Sun, 
  Grid, 
  Compass, 
  Plane, 
  Check, 
  ShieldAlert,
  Target,
  Navigation,
  AlertTriangle,
  Flag,
  FileDown
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { toast } from 'sonner';

const CATEGORY_CONFIG: Record<TacticalElementType, { label: string; color: string; border: string; bg: string; icon: React.FC<any> }> = {
  target: {
    label: 'Hostile Target',
    color: 'text-rose-400',
    border: 'border-rose-500/40',
    bg: 'bg-rose-950/40',
    icon: Target,
  },
  observation: {
    label: 'Observation Post',
    color: 'text-cyan-400',
    border: 'border-cyan-500/40',
    bg: 'bg-cyan-950/40',
    icon: Eye,
  },
  lz: {
    label: 'Landing Zone (LZ)',
    color: 'text-emerald-400',
    border: 'border-emerald-500/40',
    bg: 'bg-emerald-950/40',
    icon: Navigation,
  },
  breach: {
    label: 'Breach / Ingress',
    color: 'text-amber-400',
    border: 'border-amber-500/40',
    bg: 'bg-amber-950/40',
    icon: Flag,
  },
  hazard: {
    label: 'Hazard / Obstacle',
    color: 'text-purple-400',
    border: 'border-purple-500/40',
    bg: 'bg-purple-950/40',
    icon: AlertTriangle,
  },
  waypoint: {
    label: 'Waypoint',
    color: 'text-yellow-400',
    border: 'border-yellow-500/40',
    bg: 'bg-yellow-950/40',
    icon: MapPin,
  },
};

export const ProjectElementsManager: React.FC = () => {
  const { 
    activeJob, 
    projectMetadata, 
    tacticalElements, 
    addTacticalElement, 
    updateTacticalElement, 
    removeTacticalElement, 
    selectedElementId, 
    setSelectedElementId, 
    setFocusedElementPosition,
    environmentSettings,
    updateEnvironmentSettings,
    setIsEditProjectModalOpen,
    activeLayer,
    setActiveLayer
  } = useMissionStore();

  const { activeTool, setActiveTool, markerCategory, setMarkerCategory } = useToolStore();

  const jobId = activeJob?.job_id || 'test-new-video';
  const meta = projectMetadata[jobId] || {
    projectName: activeJob?.mission_name || `Mission ${jobId}`,
    targetLocation: 'Urban Sector 4',
    operatorCallsign: 'COMMAND-1',
    sensorModel: 'Zenmuse P1 35mm',
    reconProfile: 'Watertight Metric Mesh',
    tacticalNotes: 'Primary high-rise vertical structure survey.',
  };

  // Filter elements for active project
  const jobElements = tacticalElements.filter((el) => el.jobId === jobId);

  // Editing state for an element
  const [editingElement, setEditingElement] = useState<TacticalElement | null>(null);
  const [editName, setEditName] = useState('');
  const [editCategory, setEditCategory] = useState<TacticalElementType>('target');
  const [editNotes, setEditNotes] = useState('');

  // Quick manual add element
  const [isManualAddOpen, setIsManualAddOpen] = useState(false);
  const [manualName, setManualName] = useState('');
  const [manualCategory, setManualCategory] = useState<TacticalElementType>('target');
  const [manualX, setManualX] = useState('0');
  const [manualY, setManualY] = useState('0');
  const [manualZ, setManualZ] = useState('0');
  const [manualNotes, setManualNotes] = useState('');

  const handleStartPlacingMarker = (category: TacticalElementType) => {
    setMarkerCategory(category);
    setActiveTool('marker');
    toast.info(`Marker Mode: Click anywhere on the 3D terrain to place a "${CATEGORY_CONFIG[category].label}"`);
  };

  const handleOpenEdit = (el: TacticalElement) => {
    setEditingElement(el);
    setEditName(el.name);
    setEditCategory(el.category);
    setEditNotes(el.notes || '');
  };

  const handleSaveElementEdit = () => {
    if (!editingElement) return;
    updateTacticalElement(editingElement.id, {
      name: editName,
      category: editCategory,
      notes: editNotes,
    });
    toast.success(`Updated element "${editName}"`);
    setEditingElement(null);
  };

  const handleManualAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newEl = addTacticalElement({
      jobId,
      name: manualName || `${CATEGORY_CONFIG[manualCategory].label} ${jobElements.length + 1}`,
      category: manualCategory,
      position: {
        x: parseFloat(manualX) || 0,
        y: parseFloat(manualY) || 0,
        z: parseFloat(manualZ) || 0,
      },
      notes: manualNotes,
    });
    toast.success(`Created element "${newEl.name}"`);
    setIsManualAddOpen(false);
    setManualName('');
    setManualNotes('');
  };

  const handleFocus = (el: TacticalElement) => {
    setSelectedElementId(el.id);
    setFocusedElementPosition(el.position);
    toast.info(`Camera focused on: ${el.name}`);
  };

  const handleExportElementsJson = () => {
    const data = {
      project: meta,
      job_id: jobId,
      exported_at: new Date().toISOString(),
      elements: jobElements,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${jobId}_tactical_elements.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Tactical elements exported to JSON");
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 text-xs font-mono select-none">
      <ScrollArea className="flex-1 pr-1">
        <div className="p-3 space-y-4">
          {/* Section 1: Project Metadata Card */}
          <div className="p-3 bg-slate-900/60 border border-cyan-500/30 rounded-lg space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-cyan-400 flex items-center gap-1.5">
                <FolderEdit className="w-3.5 h-3.5" />
                PROJECT CONFIGURATION
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setIsEditProjectModalOpen(true)}
                className="h-6 text-[10px] border-cyan-500/40 text-cyan-300 hover:bg-cyan-950 px-2 py-0"
              >
                <Edit2 className="w-3 h-3 mr-1" />
                EDIT PROJECT
              </Button>
            </div>

            <div className="space-y-1 text-slate-300">
              <div className="flex justify-between border-b border-slate-800 pb-1">
                <span className="text-slate-400 text-[10px]">PROJECT NAME:</span>
                <span className="font-semibold text-cyan-300 truncate max-w-[180px]">{meta.projectName}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-1">
                <span className="text-slate-400 text-[10px]">TARGET LOCATION:</span>
                <span className="text-slate-200">{meta.targetLocation}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-1">
                <span className="text-slate-400 text-[10px]">OPERATOR CALLSIGN:</span>
                <span className="text-emerald-400">{meta.operatorCallsign}</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-1">
                <span className="text-slate-400 text-[10px]">UAV / SENSOR:</span>
                <span className="text-slate-300">{meta.sensorModel}</span>
              </div>
              {meta.tacticalNotes && (
                <div className="pt-1 text-[10px] text-slate-400 italic">
                  "{meta.tacticalNotes}"
                </div>
              )}
            </div>
          </div>

          {/* Section 2: 3D Tactical Elements / Annotations */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-cyan-400 flex items-center gap-1.5 text-[11px]">
                <Crosshair className="w-3.5 h-3.5" />
                TACTICAL 3D ELEMENTS ({jobElements.length})
              </span>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setIsManualAddOpen(true)}
                  className="h-6 text-[10px] border-slate-700 text-slate-300 hover:bg-slate-800 px-2"
                >
                  <Plus className="w-3 h-3 mr-1" />
                  MANUAL
                </Button>
                <Button
                  size="sm"
                  onClick={handleExportElementsJson}
                  variant="outline"
                  className="h-6 text-[10px] border-slate-700 text-slate-300 hover:bg-slate-800 px-1.5"
                  title="Export Elements to JSON"
                >
                  <FileDown className="w-3 h-3" />
                </Button>
              </div>
            </div>

            {/* Quick 3D Drop Marker Bar */}
            <div className="p-2 bg-slate-900/40 border border-slate-800 rounded-lg space-y-1.5">
              <span className="text-[10px] text-slate-400 block font-semibold">
                CLICK TO DROP 3D ELEMENT ON MESH:
              </span>
              <div className="grid grid-cols-3 gap-1">
                {(Object.keys(CATEGORY_CONFIG) as TacticalElementType[]).map((cat) => {
                  const cfg = CATEGORY_CONFIG[cat];
                  const Icon = cfg.icon;
                  const isActive = activeTool === 'marker' && markerCategory === cat;
                  return (
                    <button
                      key={cat}
                      onClick={() => handleStartPlacingMarker(cat)}
                      className={`flex items-center gap-1 px-1.5 py-1 rounded border text-[10px] transition-all text-left ${
                        isActive
                          ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-md shadow-cyan-900/50'
                          : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700 hover:text-white'
                      }`}
                    >
                      <Icon className={`w-3 h-3 shrink-0 ${cfg.color}`} />
                      <span className="truncate">{cfg.label.split(' ')[0]}</span>
                    </button>
                  );
                })}
              </div>
              {activeTool === 'marker' && (
                <div className="flex items-center justify-between pt-1 border-t border-slate-800">
                  <span className="text-[10px] text-cyan-300 animate-pulse flex items-center gap-1">
                    <Crosshair className="w-3 h-3 text-cyan-400" />
                    Click 3D surface to place pin...
                  </span>
                  <button
                    onClick={() => setActiveTool('none')}
                    className="text-[10px] text-slate-400 hover:text-slate-200 underline"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>

            {/* List of active elements */}
            <div className="space-y-1.5">
              {jobElements.length === 0 ? (
                <div className="p-4 text-center border border-dashed border-slate-800 rounded-lg text-slate-500 text-[11px]">
                  No tactical markers placed yet. Click a category button above or use "Manual" to add.
                </div>
              ) : (
                jobElements.map((el) => {
                  const cfg = CATEGORY_CONFIG[el.category] || CATEGORY_CONFIG.waypoint;
                  const Icon = cfg.icon;
                  const isSelected = selectedElementId === el.id;

                  return (
                    <div
                      key={el.id}
                      className={`p-2 rounded-lg border transition-all ${
                        isSelected
                          ? 'bg-cyan-950/40 border-cyan-500/60 shadow-lg shadow-cyan-950/40'
                          : 'bg-slate-900/50 border-slate-800/80 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <Icon className={`w-3.5 h-3.5 shrink-0 ${cfg.color}`} />
                          <span className="font-semibold text-slate-200 truncate">{el.name}</span>
                        </div>
                        <Badge className={`${cfg.bg} ${cfg.color} ${cfg.border} text-[9px] px-1 py-0 border shrink-0`}>
                          {cfg.label}
                        </Badge>
                      </div>

                      <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
                        <span>
                          Pos: ({el.position.x.toFixed(1)}, {el.position.y.toFixed(1)}, {el.position.z.toFixed(1)})
                        </span>
                        <div className="flex items-center gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleFocus(el)}
                            className="h-5 w-5 p-0 hover:text-cyan-300"
                            title="Focus camera"
                          >
                            <Eye className="w-3 h-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleOpenEdit(el)}
                            className="h-5 w-5 p-0 hover:text-amber-300"
                            title="Edit details"
                          >
                            <Edit2 className="w-3 h-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              removeTacticalElement(el.id);
                              toast.success(`Removed element "${el.name}"`);
                            }}
                            className="h-5 w-5 p-0 hover:text-rose-400"
                            title="Delete element"
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>

                      {el.notes && (
                        <div className="mt-1 text-[10px] text-slate-400 border-t border-slate-800/60 pt-1 italic truncate">
                          {el.notes}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Section 3: Environment & Display Elements */}
          <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg space-y-2.5">
            <span className="font-bold text-cyan-400 flex items-center gap-1.5 text-[11px]">
              <Sliders className="w-3.5 h-3.5" />
              ENVIRONMENT & VIEWPORT ELEMENTS
            </span>

            {/* Tactical Grid Settings */}
            <div className="space-y-1.5 border-b border-slate-800 pb-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 flex items-center gap-1">
                  <Grid className="w-3 h-3 text-cyan-400" />
                  Tactical Datum Grid
                </span>
                <input
                  type="checkbox"
                  checked={environmentSettings.showGrid}
                  onChange={(e) => updateEnvironmentSettings({ showGrid: e.target.checked })}
                  className="rounded border-slate-700 text-cyan-500 focus:ring-0 cursor-pointer"
                />
              </div>
              {environmentSettings.showGrid && (
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-[10px] text-slate-400">Grid Size:</span>
                  <input
                    type="range"
                    min="100"
                    max="1000"
                    step="50"
                    value={environmentSettings.gridSize}
                    onChange={(e) => updateEnvironmentSettings({ gridSize: Number(e.target.value) })}
                    className="w-full h-1 bg-slate-800 rounded appearance-none cursor-pointer accent-cyan-400"
                  />
                  <span className="text-[10px] text-cyan-300 w-12 text-right">{environmentSettings.gridSize}m</span>
                </div>
              )}
            </div>

            {/* Flight Path Overlay */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-300 flex items-center gap-1">
                <Plane className="w-3 h-3 text-cyan-400" />
                Drone Flight Path Trajectory
              </span>
              <input
                type="checkbox"
                checked={environmentSettings.showFlightPath}
                onChange={(e) => updateEnvironmentSettings({ showFlightPath: e.target.checked })}
                className="rounded border-slate-700 text-cyan-500 focus:ring-0 cursor-pointer"
              />
            </div>

            {/* Scene Lighting Intensity */}
            <div className="space-y-1 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 flex items-center gap-1">
                  <Sun className="w-3 h-3 text-cyan-400" />
                  Sunlight / Ambient Intensity
                </span>
                <span className="text-[10px] text-cyan-300">{environmentSettings.lightingIntensity.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.4"
                max="2.5"
                step="0.1"
                value={environmentSettings.lightingIntensity}
                onChange={(e) => updateEnvironmentSettings({ lightingIntensity: Number(e.target.value) })}
                className="w-full h-1 bg-slate-800 rounded appearance-none cursor-pointer accent-cyan-400"
              />
            </div>
          </div>
        </div>
      </ScrollArea>

      {/* Modal: Edit Existing Element */}
      {editingElement && (
        <Dialog open={!!editingElement} onOpenChange={() => setEditingElement(null)}>
          <DialogContent className="bg-slate-950 border border-cyan-500/40 text-white font-mono max-w-sm p-4 text-xs">
            <DialogHeader>
              <DialogTitle className="text-cyan-400 text-sm flex items-center gap-2">
                <Edit2 className="w-4 h-4" />
                EDIT TACTICAL ELEMENT
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div className="space-y-1">
                <Label className="text-slate-300 text-[11px]">Element Label</Label>
                <Input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="bg-slate-900 border-slate-700 text-cyan-300 text-xs h-7"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-slate-300 text-[11px]">Category</Label>
                <select
                  value={editCategory}
                  onChange={(e) => setEditCategory(e.target.value as TacticalElementType)}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 text-xs text-slate-200 h-7"
                >
                  {(Object.keys(CATEGORY_CONFIG) as TacticalElementType[]).map((cat) => (
                    <option key={cat} value={cat}>
                      {CATEGORY_CONFIG[cat].label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label className="text-slate-300 text-[11px]">Notes / Intelligence</Label>
                <Input
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  placeholder="Tactical details, elevation or threat status..."
                  className="bg-slate-900 border-slate-700 text-slate-200 text-xs h-7"
                />
              </div>
            </div>
            <DialogFooter className="pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditingElement(null)}
                className="h-7 border-slate-700 text-slate-300"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSaveElementEdit}
                className="h-7 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold"
              >
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Modal: Manual Add Element */}
      {isManualAddOpen && (
        <Dialog open={isManualAddOpen} onOpenChange={setIsManualAddOpen}>
          <DialogContent className="bg-slate-950 border border-cyan-500/40 text-white font-mono max-w-sm p-4 text-xs">
            <DialogHeader>
              <DialogTitle className="text-cyan-400 text-sm flex items-center gap-2">
                <Plus className="w-4 h-4" />
                MANUALLY ADD 3D ELEMENT
              </DialogTitle>
            </DialogHeader>
            <form onSubmit={handleManualAddSubmit} className="space-y-3 py-2">
              <div className="space-y-1">
                <Label className="text-slate-300 text-[11px]">Element Label *</Label>
                <Input
                  value={manualName}
                  onChange={(e) => setManualName(e.target.value)}
                  placeholder="e.g. Observation Post Beta"
                  required
                  className="bg-slate-900 border-slate-700 text-cyan-300 text-xs h-7"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-slate-300 text-[11px]">Category</Label>
                <select
                  value={manualCategory}
                  onChange={(e) => setManualCategory(e.target.value as TacticalElementType)}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 text-xs text-slate-200 h-7"
                >
                  {(Object.keys(CATEGORY_CONFIG) as TacticalElementType[]).map((cat) => (
                    <option key={cat} value={cat}>
                      {CATEGORY_CONFIG[cat].label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label className="text-slate-300 text-[11px]">Coordinates (X, Y=Alt, Z)</Label>
                <div className="grid grid-cols-3 gap-1">
                  <Input
                    value={manualX}
                    onChange={(e) => setManualX(e.target.value)}
                    placeholder="X (East)"
                    className="bg-slate-900 border-slate-700 text-slate-200 text-xs h-7"
                  />
                  <Input
                    value={manualY}
                    onChange={(e) => setManualY(e.target.value)}
                    placeholder="Y (Alt)"
                    className="bg-slate-900 border-slate-700 text-slate-200 text-xs h-7"
                  />
                  <Input
                    value={manualZ}
                    onChange={(e) => setManualZ(e.target.value)}
                    placeholder="Z (North)"
                    className="bg-slate-900 border-slate-700 text-slate-200 text-xs h-7"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-slate-300 text-[11px]">Notes</Label>
                <Input
                  value={manualNotes}
                  onChange={(e) => setManualNotes(e.target.value)}
                  placeholder="Observation notes, threat status..."
                  className="bg-slate-900 border-slate-700 text-slate-200 text-xs h-7"
                />
              </div>
              <DialogFooter className="pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsManualAddOpen(false)}
                  className="h-7 border-slate-700 text-slate-300"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  className="h-7 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold"
                >
                  Add Element
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};
