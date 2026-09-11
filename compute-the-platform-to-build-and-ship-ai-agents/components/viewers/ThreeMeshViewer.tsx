"use client";

import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useMissionStore } from '@/lib/useMissionStore';
import { useToolStore } from '@/lib/useToolStore';
import { toast } from 'sonner';
import { CameraPathOverlay } from './CameraPathOverlay';

interface ThreeMeshViewerProps {
  modelUrl?: string;
}

export const ThreeMeshViewer: React.FC<ThreeMeshViewerProps> = ({ modelUrl }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const currentMeshRef = useRef<THREE.Mesh | null>(null);
  const measurementGroupRef = useRef<THREE.Group | null>(null);
  const tacticalGroupRef = useRef<THREE.Group | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const ambientLightRef = useRef<THREE.AmbientLight | null>(null);
  const sunLightRef = useRef<THREE.DirectionalLight | null>(null);

  const { 
    activeJob,
    activeLayer, 
    setHoveredCoordinate, 
    telemetryTrack, 
    selectedKeyframeIndex,
    tacticalElements,
    addTacticalElement,
    selectedElementId,
    focusedElementPosition,
    setFocusedElementPosition,
    environmentSettings
  } = useMissionStore();
  const { activeTool, setActiveTool, addPickedPoint, pickedPoints, markerCategory } = useToolStore();


  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07090e);
    sceneRef.current = scene;

    // Tactical Ground Grid
    const grid = new THREE.GridHelper(500, 50, 0x06b6d4, 0x1e293b);
    grid.position.y = -0.5;
    scene.add(grid);
    gridRef.current = grid;

    // Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 4000);
    camera.position.set(40, 35, 60);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.01;
    controlsRef.current = controls;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);
    ambientLightRef.current = ambientLight;

    const sunLight = new THREE.DirectionalLight(0xecfeff, 2.0);
    sunLight.position.set(50, 100, 50);
    sunLight.castShadow = true;
    scene.add(sunLight);
    sunLightRef.current = sunLight;

    const fillLight = new THREE.DirectionalLight(0x0891b2, 0.8);
    fillLight.position.set(-50, 40, -50);
    scene.add(fillLight);

    const measurementGroup = new THREE.Group();
    scene.add(measurementGroup);
    measurementGroupRef.current = measurementGroup;

    const tacticalGroup = new THREE.Group();
    scene.add(tacticalGroup);
    tacticalGroupRef.current = tacticalGroup;

    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!container || !renderer || !camera) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement) {
        renderer.domElement.parentElement.removeChild(renderer.domElement);
      }
    };
  }, []);

  // Load Model
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    if (currentMeshRef.current) {
      scene.remove(currentMeshRef.current);
      currentMeshRef.current.geometry.dispose();
      currentMeshRef.current = null;
    }

    if (modelUrl) {
      const loader = new GLTFLoader();
      loader.load(
        modelUrl,
        (gltf) => {
          const model = gltf.scene;
          model.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              mesh.castShadow = true;
              mesh.receiveShadow = true;
              currentMeshRef.current = mesh;
            }
          });
          scene.add(model);

          // Auto-frame camera and position datum grid cleanly on model
          const box = new THREE.Box3().setFromObject(model);
          const center = new THREE.Vector3();
          box.getCenter(center);
          const size = new THREE.Vector3();
          box.getSize(size);
          const maxDim = Math.max(size.x, size.z, 60);

          if (controlsRef.current && cameraRef.current) {
            controlsRef.current.target.copy(center);
            cameraRef.current.position.set(
              center.x + maxDim * 0.7,
              center.y + maxDim * 0.5,
              center.z + maxDim * 0.8
            );
            cameraRef.current.near = 0.5;
            cameraRef.current.far = Math.max(3000, maxDim * 10);
            cameraRef.current.updateProjectionMatrix();
            controlsRef.current.update();
          }

          if (gridRef.current) {
            gridRef.current.position.set(center.x, box.min.y - 0.5, center.z);
          }
        },
        undefined,
        () => createFallbackTerrain(scene)
      );
    } else {
      createFallbackTerrain(scene);
    }

    function createFallbackTerrain(s: THREE.Scene) {
      const geo = new THREE.PlaneGeometry(80, 80, 48, 48);
      geo.rotateX(-Math.PI / 2);
      const pos = geo.attributes.position;
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i);
        const z = pos.getZ(i);
        const dist = Math.hypot(x, z);
        const h = Math.max(0, 8.0 - 0.25 * dist) + 1.5 * Math.sin(x * 0.2) * Math.cos(z * 0.2);
        pos.setY(i, h);
      }
      geo.computeVertexNormals();

      const mat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        roughness: 0.7,
        metalness: 0.1,
        flatShading: true,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.receiveShadow = true;
      currentMeshRef.current = mesh;
      s.add(mesh);
    }
  }, [modelUrl]);

  // Layer switches
  useEffect(() => {
    const mesh = currentMeshRef.current;
    if (!mesh) return;

    if (Array.isArray(mesh.material)) return;
    const mat = mesh.material as THREE.MeshStandardMaterial;

    if (activeLayer === 'wireframe') {
      mat.wireframe = true;
      mat.color.setHex(0x06b6d4);
    } else if (activeLayer === 'pointcloud') {
      mat.wireframe = false;
      mat.color.setHex(0x38bdf8);
    } else if (activeLayer === 'dsm') {
      mat.wireframe = false;
      mat.color.setHex(0x10b981);
    } else if (activeLayer === 'confidence') {
      mat.wireframe = false;
      mat.color.setHex(0x8b5cf6);
    } else {
      mat.wireframe = false;
      mat.color.setHex(0xffffff);
    }
    mat.needsUpdate = true;
  }, [activeLayer]);

  // Mensuration Visuals
  useEffect(() => {
    const group = measurementGroupRef.current;
    if (!group) return;

    while (group.children.length > 0) {
      const obj = group.children[0] as THREE.Mesh | THREE.Line;
      group.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
    }

    if (pickedPoints.length === 0) return;

    pickedPoints.forEach((pt, idx) => {
      const sphereGeo = new THREE.SphereGeometry(0.5, 16, 16);
      const sphereMat = new THREE.MeshBasicMaterial({
        color: idx === 0 ? 0x10b981 : 0x06b6d4,
      });
      const sphere = new THREE.Mesh(sphereGeo, sphereMat);
      sphere.position.set(pt.x, pt.z, -pt.y);
      group.add(sphere);
    });

    if (pickedPoints.length >= 2) {
      const linePoints = pickedPoints.map((p) => new THREE.Vector3(p.x, p.z, -p.y));
      if (activeTool === 'area' && pickedPoints.length >= 3) {
        linePoints.push(linePoints[0]);
      }
      const lineGeo = new THREE.BufferGeometry().setFromPoints(linePoints);
      const lineMat = new THREE.LineBasicMaterial({
        color: activeTool === 'los' ? 0x10b981 : 0x06b6d4,
        linewidth: 3,
      });
      const line = new THREE.Line(lineGeo, lineMat);
      group.add(line);
    }
  }, [pickedPoints, activeTool]);

  // Render 3D Tactical Pins & Markers
  useEffect(() => {
    const group = tacticalGroupRef.current;
    if (!group) return;

    while (group.children.length > 0) {
      const obj = group.children[0] as THREE.Object3D;
      group.remove(obj);
    }

    const currentJobId = activeJob?.job_id || 'test-new-video';
    const jobElements = tacticalElements.filter((el) => el.jobId === currentJobId);

    const colorMap: Record<string, number> = {
      target: 0xf43f5e,
      observation: 0x06b6d4,
      lz: 0x10b981,
      breach: 0xf59e0b,
      hazard: 0xa855f7,
      waypoint: 0xeab308,
    };

    jobElements.forEach((el) => {
      const hex = colorMap[el.category] || 0x06b6d4;
      const isSelected = selectedElementId === el.id;

      const pinGroup = new THREE.Group();
      pinGroup.position.set(el.position.x, el.position.y, el.position.z);

      // Vertical stem pin
      const stemGeo = new THREE.CylinderGeometry(0.12, 0.12, 3.5, 8);
      stemGeo.translate(0, 1.75, 0);
      const stemMat = new THREE.MeshBasicMaterial({ color: hex, transparent: true, opacity: 0.85 });
      const stem = new THREE.Mesh(stemGeo, stemMat);
      pinGroup.add(stem);

      // Beacon octahedron on top
      const beaconGeo = new THREE.OctahedronGeometry(isSelected ? 1.1 : 0.7, 0);
      beaconGeo.translate(0, 3.8, 0);
      const beaconMat = new THREE.MeshStandardMaterial({
        color: hex,
        emissive: hex,
        emissiveIntensity: isSelected ? 1.0 : 0.6,
        roughness: 0.2,
        metalness: 0.8,
      });
      const beacon = new THREE.Mesh(beaconGeo, beaconMat);
      pinGroup.add(beacon);

      // Ground ring pulse
      const ringGeo = new THREE.RingGeometry(0.8, 1.3, 24);
      ringGeo.rotateX(-Math.PI / 2);
      ringGeo.translate(0, 0.05, 0);
      const ringMat = new THREE.MeshBasicMaterial({
        color: hex,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: isSelected ? 0.9 : 0.5,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      pinGroup.add(ring);

      group.add(pinGroup);
    });
  }, [tacticalElements, selectedElementId, activeJob]);

  // Smooth camera pan when an element is focused from the panel
  useEffect(() => {
    if (!focusedElementPosition || !cameraRef.current || !controlsRef.current) return;
    const { x, y, z } = focusedElementPosition;
    controlsRef.current.target.set(x, y, z);
    cameraRef.current.position.set(x + 25, y + 20, z + 30);
    controlsRef.current.update();
    setFocusedElementPosition(null);
  }, [focusedElementPosition, setFocusedElementPosition]);

  // Apply environment settings (grid visibility, lighting)
  useEffect(() => {
    if (gridRef.current) {
      gridRef.current.visible = environmentSettings.showGrid;
    }
    if (ambientLightRef.current) {
      ambientLightRef.current.intensity = 1.2 * environmentSettings.lightingIntensity;
    }
    if (sunLightRef.current) {
      sunLightRef.current.intensity = 2.0 * environmentSettings.lightingIntensity;
    }
  }, [environmentSettings]);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (activeTool === 'none') return;
    const container = containerRef.current;
    const camera = cameraRef.current;
    const mesh = currentMeshRef.current;
    if (!container || !camera || !mesh) return;

    const rect = container.getBoundingClientRect();
    const mouse = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    );

    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObject(mesh, true);

    if (intersects.length > 0) {
      const hit = intersects[0].point;

      if (activeTool === 'marker') {
        const currentJobId = activeJob?.job_id || 'test-new-video';
        const cat = markerCategory || 'target';
        const labelPrefix = cat.charAt(0).toUpperCase() + cat.slice(1);
        const count = tacticalElements.filter((el) => el.jobId === currentJobId && el.category === cat).length + 1;

        const newEl = addTacticalElement({
          jobId: currentJobId,
          name: `${labelPrefix} ${count}`,
          category: cat,
          position: {
            x: Number(hit.x.toFixed(2)),
            y: Number(hit.y.toFixed(2)),
            z: Number(hit.z.toFixed(2)),
          },
          notes: `Tactical ${cat} marker placed on 3D mesh.`,
        });
        toast.success(`Placed ${cat} pin "${newEl.name}" at (${hit.x.toFixed(1)}, ${hit.y.toFixed(1)}, ${hit.z.toFixed(1)})`);
        setActiveTool('none');
        return;
      }

      addPickedPoint({
        x: Number(hit.x.toFixed(2)),
        y: Number((-hit.z).toFixed(2)),
        z: Number(hit.y.toFixed(2)),
      });
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    const camera = cameraRef.current;
    const mesh = currentMeshRef.current;
    if (!container || !camera || !mesh) return;

    const rect = container.getBoundingClientRect();
    const mouse = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    );

    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObject(mesh, true);

    if (intersects.length > 0) {
      const hit = intersects[0].point;
      setHoveredCoordinate({
        x: Number(hit.x.toFixed(2)),
        y: Number((-hit.z).toFixed(2)),
        z: Number(hit.y.toFixed(2)),
      });
    } else {
      setHoveredCoordinate(null);
    }
  };

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative cursor-crosshair select-none"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
    >
      {sceneRef.current && telemetryTrack && environmentSettings.showFlightPath && (
        <CameraPathOverlay
          scene={sceneRef.current}
          poses={telemetryTrack.poses}
          origin={{
            easting: telemetryTrack.origin_easting,
            northing: telemetryTrack.origin_northing,
            altitude: telemetryTrack.origin_altitude,
          }}
          selectedIndex={selectedKeyframeIndex}
        />
      )}
    </div>
  );
};
