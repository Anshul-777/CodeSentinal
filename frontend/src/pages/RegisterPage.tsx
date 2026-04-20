import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, Eye, EyeOff, AlertCircle, Loader2, CheckCircle, ArrowRight, ArrowLeft } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import apiClient from '@/api/client'
import toast from 'react-hot-toast'

interface FormData {
  email: string
  password: string
  full_name: string
  job_title: string
  company: string
  github_username: string
  phone: string
  organization_name: string
  use_case: string
  agree_to_terms: boolean
}

const PASSWORD_RULES = [
  { test: (p: string) => p.length >= 8, label: 'At least 8 characters' },
  { test: (p: string) => /[A-Z]/.test(p), label: 'One uppercase letter' },
  { test: (p: string) => /[a-z]/.test(p), label: 'One lowercase letter' },
  { test: (p: string) => /\d/.test(p), label: 'One number' },
  { test: (p: string) => /[!@#$%^&*()_+\-=]/.test(p), label: 'One special character' },
]

const JOB_TITLES = [
  'Security Engineer', 'DevOps Engineer', 'Software Engineer', 'Platform Engineer',
  'CTO', 'CISO', 'Engineering Manager', 'Tech Lead', 'DevSecOps Engineer', 'Other',
]

const USE_CASES = [
  'Secure our CI/CD pipeline',
  'Compliance enforcement (SOC2/HIPAA/PCI-DSS)',
  'Dependency vulnerability management',
  'Automated code security review',
  'Secret scanning and credential management',
  'Developer security education and coaching',
  'Replace/augment manual security review',
]

export default function RegisterPage() {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [form, setForm] = useState<FormData>({
    email: '', password: '', full_name: '', job_title: '',
    company: '', github_username: '', phone: '',
    organization_name: '', use_case: '', agree_to_terms: false,
  })
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  const set = (field: keyof FormData, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [field]: value }))

  const passwordStrength = PASSWORD_RULES.filter((r) => r.test(form.password)).length
  const passwordOk = passwordStrength === PASSWORD_RULES.length

  const step1Valid = form.email && form.password && passwordOk && form.full_name && form.job_title && form.company
  const step2Valid = form.organization_name && form.use_case && form.agree_to_terms

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!step2Valid) return
    setError('')
    setLoading(true)
    try {
      const { data } = await apiClient.post('/auth/register', form)
      setAuth(data.user, data.access_token, data.refresh_token)
      toast.success('Welcome to CodeSentinel!')
      navigate('/app/dashboard', { replace: true })
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail[0]?.msg || 'Validation error.')
      } else {
        setError(detail || 'Registration failed. Please try again.')
      }
      if (err.response?.status === 409) setStep(1)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-[420px] landing-gradient flex-col p-12 relative overflow-hidden flex-shrink-0">
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.4) 1px, transparent 0)', backgroundSize: '32px 32px' }}
        />
        <div className="relative z-10">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 bg-white/20 rounded-xl flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-white text-xl">CodeSentinel</span>
          </Link>
        </div>
        <div className="relative z-10 mt-auto">
          <div className="space-y-4 mb-8">
            {['5-agent parallel security pipeline', 'Real CVE lookup via OSV.dev', 'Sandboxed auto-fix with test verification', 'SOC2 / HIPAA / PCI-DSS / GDPR compliance', 'GitHub App with merge blocking', 'Local AI model support — no data leaves'].map((f) => (
              <div key={f} className="flex items-center gap-3 text-indigo-100 text-sm">
                <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                <span>{f}</span>
              </div>
            ))}
          </div>
          <div className="text-indigo-400 text-xs">Free tier — no credit card required.</div>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8 overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-lg"
        >
          <div className="lg:hidden flex items-center gap-3 mb-10 justify-center">
            <div className="w-9 h-9 bg-gradient-to-br from-sentinel-600 to-violet-600 rounded-xl flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-gray-900 text-xl">CodeSentinel</span>
          </div>

          {/* Step indicator */}
          <div className="flex items-center gap-3 mb-8">
            {[1, 2].map((s) => (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${step >= s ? 'bg-sentinel-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
                  {step > s ? <CheckCircle className="w-4 h-4" /> : s}
                </div>
                <span className={`text-sm font-medium ${step >= s ? 'text-gray-900' : 'text-gray-400'}`}>
                  {s === 1 ? 'Your account' : 'Your workspace'}
                </span>
                {s < 2 && <div className={`flex-1 h-0.5 w-12 ${step > s ? 'bg-sentinel-600' : 'bg-gray-200'}`} />}
              </div>
            ))}
          </div>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            {step === 1 ? 'Create your account' : 'Set up your workspace'}
          </h1>
          <p className="text-gray-500 mb-8">
            Already have an account?{' '}
            <Link to="/login" className="text-sentinel-600 font-medium hover:underline">Sign in</Link>
          </p>

          {error && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="mb-6 flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700"
            >
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          <form onSubmit={step === 1 ? (e) => { e.preventDefault(); if (step1Valid) setStep(2) } : handleSubmit}>
            <AnimatePresence mode="wait">
              {step === 1 && (
                <motion.div key="step1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-5">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2">
                      <label className="label">Full name <span className="text-red-500">*</span></label>
                      <input type="text" value={form.full_name} onChange={(e) => set('full_name', e.target.value)}
                        placeholder="Jane Smith" required className="input" />
                    </div>
                    <div className="col-span-2">
                      <label className="label">Work email <span className="text-red-500">*</span></label>
                      <input type="email" value={form.email} onChange={(e) => set('email', e.target.value)}
                        placeholder="jane@company.com" required className="input" autoComplete="email" />
                    </div>
                    <div>
                      <label className="label">Job title <span className="text-red-500">*</span></label>
                      <select value={form.job_title} onChange={(e) => set('job_title', e.target.value)} required className="input bg-white">
                        <option value="">Select title</option>
                        {JOB_TITLES.map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="label">Company <span className="text-red-500">*</span></label>
                      <input type="text" value={form.company} onChange={(e) => set('company', e.target.value)}
                        placeholder="Acme Corp" required className="input" />
                    </div>
                    <div>
                      <label className="label">GitHub username</label>
                      <input type="text" value={form.github_username} onChange={(e) => set('github_username', e.target.value)}
                        placeholder="githubuser" className="input" />
                    </div>
                    <div>
                      <label className="label">Phone number</label>
                      <input type="tel" value={form.phone} onChange={(e) => set('phone', e.target.value)}
                        placeholder="+1 555 0100" className="input" />
                    </div>
                    <div className="col-span-2">
                      <label className="label">Password <span className="text-red-500">*</span></label>
                      <div className="relative">
                        <input type={showPassword ? 'text' : 'password'} value={form.password}
                          onChange={(e) => set('password', e.target.value)}
                          placeholder="Create a strong password" required className="input pr-10" autoComplete="new-password" />
                        <button type="button" onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      {form.password && (
                        <div className="mt-3 space-y-1.5">
                          <div className="flex gap-1">
                            {[...Array(5)].map((_, i) => (
                              <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i < passwordStrength ? 'bg-sentinel-500' : 'bg-gray-200'}`} />
                            ))}
                          </div>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                            {PASSWORD_RULES.map((rule) => (
                              <div key={rule.label} className={`flex items-center gap-1.5 text-xs ${rule.test(form.password) ? 'text-green-600' : 'text-gray-400'}`}>
                                <CheckCircle className="w-3 h-3" />
                                {rule.label}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  <button type="submit" disabled={!step1Valid}
                    className="btn-primary w-full justify-center py-3 text-base">
                    Continue <ArrowRight className="w-4 h-4" />
                  </button>
                </motion.div>
              )}

              {step === 2 && (
                <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-5">
                  <div>
                    <label className="label">Organization / workspace name <span className="text-red-500">*</span></label>
                    <input type="text" value={form.organization_name} onChange={(e) => set('organization_name', e.target.value)}
                      placeholder="Acme Security Team" required className="input" minLength={2} />
                    <p className="text-xs text-gray-400 mt-1.5">This is how your workspace will appear to team members.</p>
                  </div>
                  <div>
                    <label className="label">Primary use case <span className="text-red-500">*</span></label>
                    <div className="space-y-2">
                      {USE_CASES.map((uc) => (
                        <label key={uc} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${form.use_case === uc ? 'border-sentinel-500 bg-sentinel-50' : 'border-gray-200 hover:border-gray-300'}`}>
                          <input type="radio" name="use_case" value={uc} checked={form.use_case === uc}
                            onChange={(e) => set('use_case', e.target.value)} className="text-sentinel-600" />
                          <span className="text-sm text-gray-700">{uc}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <label className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-all ${form.agree_to_terms ? 'border-sentinel-500 bg-sentinel-50' : 'border-gray-200'}`}>
                    <input type="checkbox" checked={form.agree_to_terms}
                      onChange={(e) => set('agree_to_terms', e.target.checked)}
                      className="mt-0.5 text-sentinel-600 rounded" required />
                    <span className="text-sm text-gray-700">
                      I agree to the Terms of Service and Privacy Policy.
                      I understand that CodeSentinel uses AI to analyze code I connect to the platform.
                    </span>
                  </label>

                  <div className="flex gap-3">
                    <button type="button" onClick={() => setStep(1)}
                      className="btn-secondary px-5">
                      <ArrowLeft className="w-4 h-4" /> Back
                    </button>
                    <button type="submit" disabled={!step2Valid || loading}
                      className="btn-primary flex-1 justify-center py-3 text-base">
                      {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating account…</> : <>Create workspace <ArrowRight className="w-4 h-4" /></>}
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </form>
        </motion.div>
      </div>
    </div>
  )
}
