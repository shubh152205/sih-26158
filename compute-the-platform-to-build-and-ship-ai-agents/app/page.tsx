"use client";

import React, { useEffect, useState } from 'react';
import { useMissionStore } from '@/lib/useMissionStore';
import { apiClient } from '@/lib/apiClient';
import { websocketClient } from '@/lib/websocketClient';

// Command Center Components
import { TopNav } from '@/components/command-center/TopNav';
import { LeftFlightPanel } from '@/components/command-center/LeftFlightPanel';
import { ViewportContainer } from '@/components/viewers/ViewportContainer';
import { RightMetricsPanel } from '@/components/command-center/RightMetricsPanel';
import { BottomTimeline } from '@/components/command-center/BottomTimeline';
import { MissionUploadModal } from '@/components/command-center/MissionUploadModal';
import { NewProjectModal } from '@/components/command-center/NewProjectModal';
import { EditProjectModal } from '@/components/command-center/EditProjectModal';

// Landing Page Components (Available as alternate view)
import { Navigation } from "@/components/landing/navigation";
import { HeroSection } from "@/components/landing/hero-section";
import { FeaturesSection } from "@/components/landing/features-section";
import { HowItWorksSection } from "@/components/landing/how-it-works-section";
import { InfrastructureSection } from "@/components/landing/infrastructure-section";
import { MetricsSection } from "@/components/landing/metrics-section";
import { IntegrationsSection } from "@/components/landing/integrations-section";
import { SecuritySection } from "@/components/landing/security-section";
import { DevelopersSection } from "@/components/landing/developers-section";
import { TestimonialsSection } from "@/components/landing/testimonials-section";
import { PricingSection } from "@/components/landing/pricing-section";
import { CtaSection } from "@/components/landing/cta-section";
import { FooterSection } from "@/components/landing/footer-section";

export default function Home() {
  const [isPlatformLandingView, setIsPlatformLandingView] = useState(false);
  const { 
    activeJob, 
    setActiveJob, 
    setJobs, 
    setTelemetryTrack, 
    setHardware, 
    updateJobProgress 
  } = useMissionStore();

  useEffect(() => {
    // 1. Initial REST polling to populate jobs, telemetry, and hardware
    const initData = async () => {
      try {
        const jobs = await apiClient.listJobs();
        setJobs(jobs);

        if (jobs.length > 0) {
          const preferredJob = jobs.find((j) => j.job_id === 'test-new-video') || jobs[jobs.length - 1];
          setActiveJob(preferredJob);

          // Fetch telemetry track for preferred job
          try {
            const track = await apiClient.getTelemetryTrack(preferredJob.job_id);
            setTelemetryTrack(track);
          } catch (e) {
            console.warn("Telemetry track not available for job yet", e);
          }
        }

        // Fetch hardware metrics
        try {
          const hw = await apiClient.getHardwareMetrics();
          setHardware(hw);
        } catch (e) {
          console.warn("Hardware endpoint error", e);
        }
      } catch (err) {
        console.warn("Initial API load error (backend might be initializing):", err);
      }
    };

    initData();

    // 2. Connect WebSocket listener for live progress
    websocketClient.connect();
    const unsub = websocketClient.subscribe((event) => {
      if (event.type === 'stage_update') {
        updateJobProgress(event.job_id, event.stage, event.progress_pct, event.message);
      }
    });

    return () => {
      unsub();
      websocketClient.disconnect();
    };
  }, [setActiveJob, setJobs, setTelemetryTrack, setHardware, updateJobProgress]);

  // If user toggles to Landing Page view
  if (isPlatformLandingView) {
    return (
      <main className="relative min-h-screen overflow-x-hidden bg-slate-950">
        <div className="fixed top-4 right-4 z-50">
          <button
            onClick={() => setIsPlatformLandingView(false)}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-mono text-xs font-bold rounded-lg shadow-xl shadow-cyan-900/50 flex items-center gap-2 transition-transform hover:scale-105"
          >
            ← BACK TO 3D COMMAND CENTER
          </button>
        </div>
        <Navigation />
        <HeroSection />
        <FeaturesSection />
        <HowItWorksSection />
        <InfrastructureSection />
        <MetricsSection />
        <IntegrationsSection />
        <SecuritySection />
        <DevelopersSection />
        <TestimonialsSection />
        <PricingSection />
        <CtaSection />
        <FooterSection />
      </main>
    );
  }

  // Primary Default View: Tactical 3D Reconstruction Command Center
  return (
    <main className="w-screen h-screen overflow-hidden flex flex-col bg-[#05070d] text-white">
      {/* Top Header Navigation */}
      <TopNav
        onTogglePlatformView={() => setIsPlatformLandingView(!isPlatformLandingView)}
        isPlatformView={isPlatformLandingView}
      />

      {/* Main Tri-Pane Viewport & Inspection Hub */}
      <div className="flex-1 flex min-h-0 relative">
        {/* Left Flight & Telemetry Panel */}
        <LeftFlightPanel />

        {/* Center 3D Interactive WebGL Viewport */}
        <div className="flex-1 h-full min-w-0 relative">
          <ViewportContainer
            modelUrl={
              activeJob
                ? apiClient.getMeshDownloadUrl(activeJob.job_id)
                : "/api/v1/export/demo-mission-alpha/mesh"
            }
          />
        </div>

        {/* Right Tactical Mensuration & Audit Hub */}
        <RightMetricsPanel />
      </div>

      {/* Bottom 6-Stage Photogrammetry Pipeline Stepper */}
      <BottomTimeline />

      {/* Mission & Project Modals */}
      <NewProjectModal />
      <EditProjectModal />
      <MissionUploadModal />
    </main>
  );
}
