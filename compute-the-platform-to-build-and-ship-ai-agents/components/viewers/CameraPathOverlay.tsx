"use client";

import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { TelemetryPose } from '@/lib/apiClient';

interface CameraPathOverlayProps {
  scene: THREE.Scene;
  poses: TelemetryPose[];
  origin: { easting: number; northing: number; altitude: number };
  selectedIndex: number;
}

export const CameraPathOverlay: React.FC<CameraPathOverlayProps> = ({
  scene,
  poses,
  origin,
  selectedIndex,
}) => {
  const groupRef = useRef<THREE.Group | null>(null);

  useEffect(() => {
    if (!poses || poses.length === 0) return;

    if (groupRef.current) {
      scene.remove(groupRef.current);
    }

    const group = new THREE.Group();
    groupRef.current = group;

    // 1. Build continuous 3D flight trajectory curve
    const points: THREE.Vector3[] = poses.map((p) => {
      const x = p.utm_easting - origin.easting;
      const y = p.utm_altitude - origin.altitude;
      const z = -(p.utm_northing - origin.northing);
      return new THREE.Vector3(x, y, z);
    });

    const curve = new THREE.CatmullRomCurve3(points);
    const curvePoints = curve.getPoints(Math.max(50, points.length * 4));
    const geometry = new THREE.BufferGeometry().setFromPoints(curvePoints);

    // Glowing tactical flight path line
    const material = new THREE.LineBasicMaterial({
      color: 0x06b6d4,
      linewidth: 2,
      transparent: true,
      opacity: 0.85,
    });
    const splineLine = new THREE.Line(geometry, material);
    group.add(splineLine);

    // 2. Camera viewing frustum cones for keyframes
    points.forEach((pt, idx) => {
      const isSelected = idx === selectedIndex;
      const coneGeo = new THREE.ConeGeometry(isSelected ? 1.2 : 0.6, isSelected ? 2.5 : 1.2, 4);
      coneGeo.rotateX(Math.PI);

      const coneMat = new THREE.MeshBasicMaterial({
        color: isSelected ? 0x10b981 : 0x0891b2,
        wireframe: true,
        transparent: true,
        opacity: isSelected ? 1.0 : 0.6,
      });

      const cone = new THREE.Mesh(coneGeo, coneMat);
      cone.position.copy(pt);
      group.add(cone);
    });

    scene.add(group);

    return () => {
      if (groupRef.current) {
        scene.remove(groupRef.current);
      }
    };
  }, [scene, poses, origin, selectedIndex]);

  return null;
};
