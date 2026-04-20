import { useRef, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform, useSpring, AnimatePresence } from 'framer-motion'
import {
  Shield, Zap, GitBranch, Lock, CheckCircle, ArrowRight,
  Code2, Bug, Wrench, Activity, Users, Globe, ChevronDown,
  Star, Cpu, Package, AlertTriangle, Play,
} from 'lucide-react'

const STATS = [
  { value: '742%', label: 'Increase in supply chain attacks 2020–2024' },
  { value: '$4.88M', label: 'Average cost of a security breach (IBM, 2024)' },
  { value: '100:1', label: 'Developer-to-security-engineer ratio' },
  { value: '78%', label: 'Vulnerabilities preventable at code review' },
]

const FEATURES = [
  {
    icon: Bug,
    title: 'Static + Semantic Analysis',
    description: 'Agent 1 combines Bandit, AST analysis, and LLM semantic reasoning to catch vulnerabilities that pattern matching misses — race conditions, auth bypasses, and business logic errors.',
    color: 'from-red-500 to-rose-600',
  },
  {
    icon: Package,
    title: 'Dependency Intelligence',
    description: 'Agent 2 queries OSV.dev for real CVEs in your dependencies, checks license risks, and generates an SBOM in SPDX format — all without storing your code.',
    color: 'from-orange-500 to-amber-600',
  },
  {
    icon: Code2,
    title: 'Business Logic Review',
    description: 'Agent 3 reads your code the way a senior security engineer does — spotting IDOR, missing auth checks, financial logic errors, and API contract violations.',
    color: 'from-blue-500 to-indigo-600',
  },
  {
    icon: Wrench,
    title: 'Sandboxed Auto-Fix',
    description: 'Agent 4 generates a real patch, applies it in isolation, runs your test suite, and only marks it verified if validation passes. Never fakes success.',
    color: 'from-green-500 to-emerald-600',
  },
  {
    icon: CheckCircle,
    title: 'Compliance Enforcement',
    description: 'Agent 5 checks SOC2, HIPAA, PCI-DSS 4.0, and GDPR against your code changes — with plain-English explanations of each violation and its regulatory impact.',
    color: 'from-purple-500 to-violet-600',
  },
  {
    icon: Shield,
    title: 'Secret Scanning',
    description: 'Real-time detection of hardcoded credentials, API keys, tokens, and connection strings across every file change — before they reach production.',
    color: 'from-sentinel-500 to-blue-600',
  },
]

const PIPELINE_STEPS = [
  { agent: 'Agent 1', name: 'Static Analysis', icon: Bug, color: 'bg-red-500', desc: 'Bandit + AST + LLM' },
  { agent: 'Agent 2', name: 'Dependencies', icon: Package, color: 'bg-orange-500', desc: 'OSV.dev CVE lookup' },
  { agent: 'Agent 3', name: 'Business Logic', icon: Code2, color: 'bg-blue-500', desc: 'Semantic reasoning' },
  { agent: 'Agent 4', name: 'Auto-Fix', icon: Wrench, color: 'bg-green-500', desc: 'Sandbox + verify' },
  { agent: 'Agent 5', name: 'Compliance', icon: CheckCircle, color: 'bg-purple-500', desc: 'SOC2/HIPAA/PCI/GDPR' },
]

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: heroRef })
  const y = useTransform(scrollYProgress, [0, 1], ['0%', '30%'])
  const opacity = useTransform(scrollYProgress, [0, 0.6], [1, 0])
  const [activeAgent, setActiveAgent] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveAgent((prev) => (prev + 1) % PIPELINE_STEPS.length)
    }, 1800)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-white overflow-x-hidden">
      {/* ── Navbar ─────────────────────────────────────────────── */}
      <nav className="fixed top-0 w-full z-50 bg-white/90 backdrop-blur-md border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-gradient-to-br from-sentinel-600 to-violet-600 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-gray-900 text-lg">CodeSentinel</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
            <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
            <a href="#pipeline" className="hover:text-gray-900 transition-colors">How it works</a>
            <a href="#stats" className="hover:text-gray-900 transition-colors">Why now</a>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
              Sign in
            </Link>
            <Link to="/register" className="btn-primary text-sm">
              Get started free
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────── */}
      <section ref={heroRef} className="relative min-h-screen flex items-center overflow-hidden landing-gradient pt-16">
        {/* Mesh background */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-violet-500/20 rounded-full blur-3xl" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-sentinel-600/10 rounded-full blur-3xl" />
          {/* Grid */}
          <div
            className="absolute inset-0 opacity-[0.06]"
            style={{
              backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)',
              backgroundSize: '60px 60px',
            }}
          />
        </div>

        <motion.div style={{ y, opacity }} className="relative z-10 max-w-7xl mx-auto px-6 py-32 w-full">
          <div className="max-w-4xl mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-2 px-4 py-2 glass rounded-full text-sm text-indigo-200 mb-8"
            >
              <Zap className="w-4 h-4 text-yellow-400" />
              <span>5-Agent AI Security Pipeline — Real Detection, Real Fixes</span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1 }}
              className="text-5xl md:text-7xl font-black leading-[1.05] mb-8"
            >
              <span className="text-white">Your code's</span>{' '}
              <span className="text-gradient-landing">always-on</span>
              <br />
              <span className="text-white">security engineer</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.25 }}
              className="text-lg md:text-xl text-indigo-200 mb-10 max-w-2xl mx-auto leading-relaxed"
            >
              CodeSentinel runs a 5-agent AI pipeline on every pull request — scanning for vulnerabilities,
              checking dependencies against real CVEs, enforcing compliance, and auto-fixing what it finds.
              Integrated directly into GitHub.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.35 }}
              className="flex flex-col sm:flex-row items-center justify-center gap-4"
            >
              <Link
                to="/register"
                className="flex items-center gap-2 px-8 py-4 bg-white text-sentinel-700 font-bold text-base rounded-xl hover:bg-indigo-50 transition-colors shadow-elevated"
              >
                Start for free
                <ArrowRight className="w-5 h-5" />
              </Link>
              <a
                href="#pipeline"
                className="flex items-center gap-2 px-8 py-4 glass text-white font-semibold text-base rounded-xl hover:bg-white/15 transition-colors"
              >
                <Play className="w-4 h-4" />
                See how it works
              </a>
            </motion.div>
          </div>

          {/* Pipeline preview */}
          <motion.div
            initial={{ opacity: 0, y: 60 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.5 }}
            className="mt-20 max-w-3xl mx-auto"
          >
            <div className="glass rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-yellow-400" />
                <div className="w-3 h-3 rounded-full bg-green-400" />
                <span className="ml-3 text-sm text-indigo-300 font-mono">codesentinel — pipeline running</span>
              </div>
              <div className="flex items-center gap-2">
                {PIPELINE_STEPS.map((step, i) => {
                  const Icon = step.icon
                  const isActive = i === activeAgent
                  const isDone = i < activeAgent
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center gap-2">
                      <motion.div
                        animate={isActive ? { scale: [1, 1.1, 1] } : {}}
                        transition={{ duration: 0.5, repeat: isActive ? Infinity : 0 }}
                        className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-500 ${
                          isDone ? 'bg-green-500' : isActive ? step.color : 'bg-white/10'
                        }`}
                      >
                        {isDone ? (
                          <CheckCircle className="w-5 h-5 text-white" />
                        ) : (
                          <Icon className={`w-5 h-5 ${isActive ? 'text-white' : 'text-white/40'}`} />
                        )}
                      </motion.div>
                      <div className="text-center">
                        <div className={`text-[10px] font-bold ${isActive ? 'text-white' : isDone ? 'text-green-400' : 'text-white/40'}`}>
                          {step.agent}
                        </div>
                        <div className={`text-[9px] mt-0.5 hidden sm:block ${isActive ? 'text-indigo-200' : 'text-white/30'}`}>
                          {step.desc}
                        </div>
                      </div>
                      {i < PIPELINE_STEPS.length - 1 && (
                        <div className={`absolute mt-5 w-8 h-0.5 translate-x-14 hidden sm:block transition-colors duration-500 ${isDone ? 'bg-green-500/50' : 'bg-white/10'}`} />
                      )}
                    </div>
                  )
                })}
              </div>
              <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between text-xs text-indigo-300">
                <span className="font-mono">PR #42 — feature/payment-api</span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  Scanning…
                </span>
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 text-white/50"
        >
          <ChevronDown className="w-6 h-6" />
        </motion.div>
      </section>

      {/* ── Stats ──────────────────────────────────────────────── */}
      <section id="stats" className="py-24 bg-gray-950">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              The problem is already here
            </h2>
            <p className="text-gray-400 text-lg max-w-2xl mx-auto">
              Software supply chain attacks are accelerating. Manual security review is statistically impossible.
              The window for prevention closes at merge.
            </p>
          </motion.div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {STATS.map((stat, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.5 }}
                className="text-center p-8 rounded-2xl bg-white/5 border border-white/10"
              >
                <div className="text-4xl md:text-5xl font-black text-white mb-3">{stat.value}</div>
                <div className="text-sm text-gray-400 leading-relaxed">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pipeline explainer ─────────────────────────────────── */}
      <section id="pipeline" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-20"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-sentinel-50 text-sentinel-700 rounded-full text-sm font-medium mb-6">
              <Activity className="w-4 h-4" />
              Real-time 5-Agent Pipeline
            </div>
            <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-6">
              Every pull request. <br />
              <span className="gradient-text">Every agent. In parallel.</span>
            </h2>
            <p className="text-gray-500 text-lg max-w-2xl mx-auto">
              When a PR opens, all five agents activate simultaneously. Results post back to GitHub
              as a check run — with merge blocking for critical issues.
            </p>
          </motion.div>

          {/* Flow diagram */}
          <div className="relative">
            <div className="flex items-start gap-4 overflow-x-auto pb-6">
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                className="flex-shrink-0 bg-gray-900 text-white rounded-2xl p-5 w-48"
              >
                <GitBranch className="w-6 h-6 mb-3 text-sentinel-400" />
                <div className="font-bold text-sm mb-1">PR Opened</div>
                <div className="text-xs text-gray-400">GitHub webhook → CodeSentinel backend</div>
              </motion.div>

              <div className="flex-shrink-0 flex items-center self-center">
                <div className="w-12 h-0.5 bg-sentinel-300" />
                <div className="w-0 h-0 border-t-4 border-b-4 border-l-8 border-transparent border-l-sentinel-400" />
              </div>

              <div className="flex-1 grid grid-cols-1 sm:grid-cols-5 gap-3">
                {PIPELINE_STEPS.map((step, i) => {
                  const Icon = step.icon
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 20 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.1 }}
                      className="bg-white border border-gray-200 rounded-xl p-4 shadow-card hover:shadow-card-hover transition-shadow"
                    >
                      <div className={`w-8 h-8 ${step.color} rounded-lg flex items-center justify-center mb-3`}>
                        <Icon className="w-4 h-4 text-white" />
                      </div>
                      <div className="text-xs font-bold text-gray-500 mb-1">{step.agent}</div>
                      <div className="text-sm font-semibold text-gray-900 mb-1">{step.name}</div>
                      <div className="text-xs text-gray-500">{step.desc}</div>
                    </motion.div>
                  )
                })}
              </div>

              <div className="flex-shrink-0 flex items-center self-center">
                <div className="w-12 h-0.5 bg-sentinel-300" />
                <div className="w-0 h-0 border-t-4 border-b-4 border-l-8 border-transparent border-l-sentinel-400" />
              </div>

              <motion.div
                initial={{ opacity: 0, x: 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                className="flex-shrink-0 bg-green-50 border border-green-200 rounded-2xl p-5 w-48"
              >
                <CheckCircle className="w-6 h-6 mb-3 text-green-600" />
                <div className="font-bold text-sm text-green-900 mb-1">Results Posted</div>
                <div className="text-xs text-green-700">PR check + review + merge gate</div>
              </motion.div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features grid ──────────────────────────────────────── */}
      <section id="features" className="py-24 bg-gray-50">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-black text-gray-900 mb-4">
              Not a scanner. A security platform.
            </h2>
            <p className="text-gray-500 text-lg max-w-2xl mx-auto">
              CodeSentinel combines static analysis tools, real CVE databases, LLM reasoning,
              and sandbox verification into a production-grade system.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((feature, i) => {
              const Icon = feature.icon
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.08 }}
                  className="card card-hover p-6"
                >
                  <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-5 shadow-sm`}>
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  <h3 className="text-base font-bold text-gray-900 mb-2">{feature.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{feature.description}</p>
                </motion.div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── CTA ────────────────────────────────────────────────── */}
      <section className="py-32 landing-gradient">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="glass rounded-3xl p-16"
          >
            <Shield className="w-16 h-16 text-white/80 mx-auto mb-8" />
            <h2 className="text-4xl md:text-5xl font-black text-white mb-6 leading-tight">
              Start securing your code today.
            </h2>
            <p className="text-indigo-200 text-lg mb-10 max-w-xl mx-auto">
              Free tier. No credit card. Connect GitHub in 2 minutes.
              Local AI models supported — your code never leaves your environment.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                to="/register"
                className="flex items-center gap-2 px-8 py-4 bg-white text-sentinel-700 font-bold text-lg rounded-xl hover:bg-indigo-50 transition-colors shadow-elevated"
              >
                Create free account
                <ArrowRight className="w-5 h-5" />
              </Link>
            </div>
            <div className="mt-8 flex items-center justify-center gap-6 text-sm text-indigo-300">
              <span className="flex items-center gap-1.5"><CheckCircle className="w-4 h-4 text-green-400" /> Free tier always available</span>
              <span className="flex items-center gap-1.5"><Lock className="w-4 h-4 text-blue-400" /> Local AI model support</span>
              <span className="flex items-center gap-1.5"><Zap className="w-4 h-4 text-yellow-400" /> Real-time GitHub integration</span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────── */}
      <footer className="bg-gray-950 py-12 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-gradient-to-br from-sentinel-600 to-violet-600 rounded-lg flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-white">CodeSentinel</span>
          </div>
          <div className="text-sm text-gray-500">
            Built with real security tools. No dummy data. No fake integrations.
          </div>
          <div className="flex items-center gap-6 text-sm text-gray-500">
            <Link to="/login" className="hover:text-gray-300 transition-colors">Sign in</Link>
            <Link to="/register" className="hover:text-gray-300 transition-colors">Register</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
