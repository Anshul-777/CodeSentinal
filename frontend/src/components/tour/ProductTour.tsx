import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import {
  X, ArrowRight, ArrowLeft, Shield, CheckCircle,
  Lightbulb, ChevronRight,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import apiClient from '@/api/client'
import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'

export interface TourStep {
  id: string
  route: string          // The app route this step applies to
  targetSelector?: string  // CSS selector to highlight (optional)
  title: string
  content: string
  position: 'top' | 'bottom' | 'left' | 'right' | 'center'
  icon?: 'shield' | 'check' | 'lightbulb'
  isWelcome?: boolean
}

const TOUR_STEPS: TourStep[] = [
  {
    id: 'welcome',
    route: '/app/dashboard',
    title: 'Welcome to CodeSentinel',
    content: 'This is a guided tour of the platform. You\'re logged in as a test account with pre-populated data from a real GitHub repository with intentional vulnerabilities. Click Next to explore each feature.',
    position: 'center',
    icon: 'shield',
    isWelcome: true,
  },
  {
    id: 'dashboard-overview',
    route: '/app/dashboard',
    targetSelector: '[data-tour="stat-cards"]',
    title: 'Dashboard Overview',
    content: 'This dashboard shows your real-time security posture. The numbers here are pulled live from the database — open findings, repositories connected, scans run, and risk scores. Nothing is mocked.',
    position: 'bottom',
    icon: 'lightbulb',
  },
  {
    id: 'dashboard-charts',
    route: '/app/dashboard',
    targetSelector: '[data-tour="scan-activity"]',
    title: 'Scan Activity Chart',
    content: 'This chart shows actual scan activity over time. It populates as you trigger scans — either manually or automatically when you open a pull request on a connected repository.',
    position: 'top',
    icon: 'lightbulb',
  },
  {
    id: 'repositories',
    route: '/app/repositories',
    title: 'Connect Your GitHub Repository',
    content: 'This is where you connect your GitHub repositories via GitHub App installation. Click "Connect GitHub" → install the app on your repo → it appears here automatically. The test account has a demo repo pre-connected.',
    position: 'center',
    icon: 'shield',
  },
  {
    id: 'scans',
    route: '/app/scans',
    title: 'Scan History',
    content: 'Every scan triggered — by a PR webhook, a push event, or manually — appears here. Click any scan to see the live 5-agent pipeline, individual agent results, and all findings. Scans that block merges are highlighted in red.',
    position: 'center',
    icon: 'lightbulb',
  },
  {
    id: 'scan-pipeline',
    route: '/app/scans',
    title: 'The 5-Agent Pipeline',
    content: 'When you open a scan, you\'ll see 5 agents running in parallel: Static Analysis (Bandit + LLM), Dependency Intelligence (OSV.dev CVE lookup), Business Logic Review, Auto-Fix Agent, and Compliance (SOC2/HIPAA/PCI-DSS/GDPR). Each agent updates its state in real time — polling every 3 seconds while running.',
    position: 'center',
    icon: 'shield',
  },
  {
    id: 'findings',
    route: '/app/findings',
    title: 'Findings — Real Vulnerabilities',
    content: 'Every finding has: file path + line number, severity (CVSS scored), a "Why was this flagged?" explanation in plain English, a business risk assessment for executives, and a recommendation. No generic one-liner labels here.',
    position: 'center',
    icon: 'shield',
  },
  {
    id: 'autofix',
    route: '/app/autofix',
    title: 'Auto-Fix with Sandbox Verification',
    content: 'Agent 4 generates real patches. Each fix goes through a 3-step validation: syntax check → flake8 lint → pytest (if tests exist). Only fixes where all checks pass are marked "Verified". Rejected fixes explain why they failed. You can then apply verified fixes directly to your repository.',
    position: 'center',
    icon: 'lightbulb',
  },
  {
    id: 'compliance',
    route: '/app/compliance',
    title: 'Compliance Enforcement',
    content: 'Agent 5 checks code against real rule packs: SOC2 CC6.1–CC8.1, HIPAA 164.312, PCI-DSS 4.0 Req 6/8, and GDPR Article 32. Each violation includes the regulation clause, what the code violates, and what must change. Compliance scores are calculated from actual pass/fail rule counts.',
    position: 'center',
    icon: 'check',
  },
  {
    id: 'dependencies',
    route: '/app/dependencies',
    title: 'Real CVE Detection',
    content: 'Agent 2 queries OSV.dev (Google\'s open vulnerability database — free, no API key required) for every package version found in your manifests. It checks requirements.txt, package.json, go.mod, and more. Vulnerable packages show the exact CVE ID and the fixed version to upgrade to.',
    position: 'center',
    icon: 'lightbulb',
  },
  {
    id: 'secrets',
    route: '/app/secrets',
    title: 'Secret Scanning',
    content: '15+ credential pattern types are scanned: AWS keys, GitHub PATs, Stripe live keys, OpenAI keys, JWT secrets, private keys, database URIs, and more. Secrets are always critical severity and include instructions to rotate credentials and purge git history.',
    position: 'center',
    icon: 'shield',
  },
  {
    id: 'models',
    route: '/app/models',
    title: 'AI Model Configuration',
    content: 'CodeSentinel uses a fallback chain: Ollama (local, free) → Groq (free tier) → OpenAI → Anthropic. You can test each provider from this page. If no providers are available, static analysis tools (Bandit, OSV.dev) still work — the LLM layer is additive, not blocking.',
    position: 'center',
    icon: 'lightbulb',
  },
  {
    id: 'audit',
    route: '/app/audit',
    title: 'Immutable Audit Trail',
    content: 'Every login, scan trigger, fix application, policy change, and permission update is recorded here. Audit logs are append-only and include IP address, actor, and result. This is what compliance auditors look at.',
    position: 'center',
    icon: 'check',
  },
  {
    id: 'complete',
    route: '/app/dashboard',
    title: 'Tour Complete',
    content: 'You\'ve seen the key features of CodeSentinel. Now connect your own GitHub repository, install the GitHub App, and open a pull request to see a real scan run on your actual code. Everything you saw in this tour is real — no mocked data.',
    position: 'center',
    icon: 'check',
    isWelcome: true,
  },
]

function TourPopover({
  step,
  stepIndex,
  totalSteps,
  onNext,
  onPrev,
  onDismiss,
  targetRect,
}: {
  step: TourStep
  stepIndex: number
  totalSteps: number
  onNext: () => void
  onPrev: () => void
  onDismiss: () => void
  targetRect?: DOMRect | null
}) {
  const isFirst = stepIndex === 0
  const isLast = stepIndex === totalSteps - 1

  const IconComponent = step.icon === 'shield' ? Shield : step.icon === 'check' ? CheckCircle : Lightbulb
  const iconColor = step.icon === 'shield' ? 'text-sentinel-600' : step.icon === 'check' ? 'text-green-600' : 'text-amber-600'
  const iconBg = step.icon === 'shield' ? 'bg-sentinel-100' : step.icon === 'check' ? 'bg-green-100' : 'bg-amber-100'

  // Center positioning for steps without a target
  const popoverStyle: React.CSSProperties = step.isWelcome || !targetRect
    ? { position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 1001 }
    : {}

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: 8 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      style={popoverStyle}
      className="w-[380px] bg-white rounded-2xl shadow-elevated border border-gray-200 overflow-hidden"
    >
      {/* Header */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl ${iconBg} flex items-center justify-center flex-shrink-0`}>
              <IconComponent className={`w-5 h-5 ${iconColor}`} />
            </div>
            <div>
              <div className="font-bold text-gray-900 leading-tight">{step.title}</div>
              <div className="text-xs text-gray-500 mt-0.5">Step {stepIndex + 1} of {totalSteps}</div>
            </div>
          </div>
          <button onClick={onDismiss} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 flex-shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mx-5 h-1 bg-gray-100 rounded-full mb-4">
        <div
          className="h-full bg-sentinel-500 rounded-full transition-all duration-500"
          style={{ width: `${((stepIndex + 1) / totalSteps) * 100}%` }}
        />
      </div>

      {/* Content */}
      <div className="px-5 pb-5">
        <p className="text-sm text-gray-600 leading-relaxed">{step.content}</p>

        {/* Actions */}
        <div className="flex items-center justify-between mt-5">
          <button
            onClick={onDismiss}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            {!isFirst && (
              <button onClick={onPrev} className="btn-secondary text-sm px-3 py-2">
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
            )}
            <button onClick={onNext} className="btn-primary text-sm">
              {isLast ? (
                <><CheckCircle className="w-3.5 h-3.5" /> Finish</>
              ) : (
                <>Next <ArrowRight className="w-3.5 h-3.5" /></>
              )}
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export default function ProductTour() {
  const { user, setUser } = useAuthStore()
  const location = useLocation()
  const [active, setActive] = useState(false)
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null)

  const tourMutation = useMutation({
    mutationFn: (data: { tour_completed: boolean; tour_step: number }) =>
      apiClient.patch('/auth/tour', data),
    onSuccess: (res) => {
      setUser({ ...user!, tour_completed: res.data.tour_completed, tour_step: res.data.tour_step })
    },
  })

  // Only show tour for test users and new accounts (tour not completed)
  const shouldShowTour = user && !user.tour_completed

  useEffect(() => {
    if (shouldShowTour) {
      // Small delay to let page render
      const timer = setTimeout(() => setActive(true), 1000)
      return () => clearTimeout(timer)
    }
  }, [shouldShowTour])

  // Filter steps to current route
  const routeSteps = TOUR_STEPS.filter(s => s.route === location.pathname)

  // All steps flattened (we navigate between routes as user moves through tour)
  const allSteps = TOUR_STEPS
  const currentStep = allSteps[currentStepIndex]

  useEffect(() => {
    if (!active || !currentStep?.targetSelector) {
      setTargetRect(null)
      return
    }
    const el = document.querySelector(currentStep.targetSelector)
    if (el) {
      setTargetRect(el.getBoundingClientRect())
    } else {
      setTargetRect(null)
    }
  }, [active, currentStepIndex, location.pathname, currentStep])

  const handleNext = () => {
    if (currentStepIndex < allSteps.length - 1) {
      const nextStep = allSteps[currentStepIndex + 1]
      const nextIndex = currentStepIndex + 1

      // Navigate to the next step's route if different
      if (nextStep.route !== location.pathname) {
        import('react-router-dom').then(({ useNavigate }) => {
          // We'll handle navigation through the URL change
        })
        window.history.pushState({}, '', nextStep.route)
        window.dispatchEvent(new PopStateEvent('popstate'))
      }

      setCurrentStepIndex(nextIndex)
      tourMutation.mutate({ tour_completed: false, tour_step: nextIndex })
    } else {
      handleDismiss()
    }
  }

  const handlePrev = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1)
    }
  }

  const handleDismiss = () => {
    setActive(false)
    tourMutation.mutate({ tour_completed: true, tour_step: allSteps.length })
  }

  if (!active || !shouldShowTour) return null

  // Only render on the correct route
  if (currentStep && currentStep.route !== location.pathname) {
    return null
  }

  return (
    <AnimatePresence>
      {active && currentStep && (
        <>
          {/* Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 backdrop-blur-[1px] z-[1000]"
            onClick={() => {}} // Prevent click-through to dismiss
          />

          {/* Highlight box around target element */}
          {targetRect && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="fixed z-[1000] rounded-xl ring-4 ring-sentinel-500 ring-offset-2 pointer-events-none"
              style={{
                top: targetRect.top - 6,
                left: targetRect.left - 6,
                width: targetRect.width + 12,
                height: targetRect.height + 12,
              }}
            />
          )}

          {/* Popover */}
          <TourPopover
            step={currentStep}
            stepIndex={currentStepIndex}
            totalSteps={allSteps.length}
            onNext={handleNext}
            onPrev={handlePrev}
            onDismiss={handleDismiss}
            targetRect={targetRect}
          />
        </>
      )}
    </AnimatePresence>
  )
}
