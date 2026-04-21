// ── Auth ──────────────────────────────────────────────────────────────────────
export interface User {
  id: string
  email: string
  full_name: string
  job_title?: string
  company?: string
  github_username?: string
  phone?: string
  avatar_url?: string
  user_timezone?: string
  is_test_user: boolean
  tour_completed: boolean
  tour_step: number
  notify_email: boolean
  notify_slack: boolean
  notify_critical_only?: boolean
  api_key_prefix?: string
  created_at: string
  organization?: Organization | null
}

export interface Organization {
  id: string
  name: string
  slug: string
  plan: 'free' | 'pro' | 'enterprise'
}

export interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

// ── Repository ────────────────────────────────────────────────────────────────
export interface Repository {
  id: string
  provider: 'github' | 'gitlab' | 'bitbucket'
  name: string
  full_name: string
  description?: string
  url?: string
  default_branch: string
  language?: string
  is_private: boolean
  stars_count: number
  scan_enabled: boolean
  scan_on_pr: boolean
  scan_on_push: boolean
  auto_fix_enabled: boolean
  auto_fix_mode: 'suggest' | 'auto_commit' | 'auto_pr'
  block_on_critical: boolean
  block_on_high: boolean
  block_on_secret: boolean
  require_review_threshold: string
  compliance_profiles: string[]
  connection_status: 'connected' | 'disconnected' | 'error'
  connection_error?: string
  webhook_active: boolean
  has_write_access: boolean
  has_check_access: boolean
  can_create_pr: boolean
  total_scans: number
  total_findings: number
  open_findings: number
  last_scan_at?: string
  last_scan_risk_score?: number
  created_at: string
}

// ── Scan ──────────────────────────────────────────────────────────────────────
export type ScanStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'blocked'
export type AgentState = 'waiting' | 'running' | 'completed' | 'failed' | 'skipped'
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export interface AgentStates {
  static: AgentState
  dependency: AgentState
  business_logic: AgentState
  autofix: AgentState
  compliance: AgentState
}

export interface ComplianceScore {
  passed: number
  failed: number
  score: number
  notes?: string
  findings_count?: number
}

export interface Scan {
  id: string
  repository_id: string
  trigger: 'pr' | 'push' | 'manual' | 'scheduled'
  pr_number?: number
  pr_title?: string
  pr_url?: string
  pr_author?: string
  branch?: string
  base_branch?: string
  commit_sha?: string
  commit_message?: string
  compare_url?: string
  status: ScanStatus
  risk_score?: number
  risk_level?: string
  findings_total: number
  findings_critical: number
  findings_high: number
  findings_medium: number
  findings_low: number
  findings_info: number
  secrets_found: number
  dependencies_vulnerable: number
  fixes_available: number
  fixes_applied: number
  agent_states: AgentStates
  agent_results?: Record<string, any>
  agent_errors?: Record<string, string>
  agent_durations?: Record<string, number>
  compliance_results?: Record<string, ComplianceScore>
  merge_blocked: boolean
  merge_block_reason?: string
  check_run_url?: string
  ai_provider?: string
  ai_model?: string
  ai_tokens_used: number
  files_scanned_count: number
  lines_scanned: number
  duration_seconds?: number
  queued_at?: string
  started_at?: string
  completed_at?: string
  created_at: string
}

// ── Finding ───────────────────────────────────────────────────────────────────
export type FindingStatus = 'open' | 'fixed' | 'ignored' | 'false_positive' | 'accepted_risk'
export type AgentType = 'static' | 'dependency' | 'business_logic' | 'compliance' | 'secret'

export interface Finding {
  id: string
  scan_id: string
  repository_id: string
  agent_type: AgentType
  rule_id?: string
  cve_id?: string
  cwe_id?: string
  owasp_category?: string
  title: string
  description: string
  business_risk?: string
  why_flagged?: string
  recommendation?: string
  references?: string[]
  file_path?: string
  line_start?: number
  line_end?: number
  code_snippet?: string
  code_context?: string
  severity: Severity
  cvss_score?: number
  cvss_vector?: string
  confidence: 'high' | 'medium' | 'low'
  category?: string
  compliance_frameworks?: string[]
  compliance_details?: Record<string, any>
  dependency_name?: string
  dependency_version?: string
  dependency_fixed_version?: string
  dependency_ecosystem?: string
  secret_type?: string
  status: FindingStatus
  is_false_positive: boolean
  false_positive_reason?: string
  fix_available: boolean
  fix_complexity?: string
  first_seen_at?: string
  last_seen_at?: string
  resolved_at?: string
  created_at: string
}

// ── Fix ───────────────────────────────────────────────────────────────────────
export type FixStatus = 'pending' | 'sandbox_testing' | 'verified' | 'applying' | 'applied' | 'rejected' | 'user_rejected'

export interface Fix {
  id: string
  finding_id: string
  scan_id: string
  fix_type: 'automated' | 'suggested' | 'manual'
  fix_strategy?: string
  file_path?: string
  original_code?: string
  fixed_code?: string
  diff_patch?: string
  diff_stats?: { lines_added: number; lines_removed: number }
  description?: string
  why_safe?: string
  step_by_step?: string
  sandbox_status: 'pending' | 'running' | 'passed' | 'failed' | 'skipped'
  sandbox_test_output?: string
  sandbox_lint_output?: string
  sandbox_duration_seconds?: number
  sandbox_checks_passed?: string[]
  sandbox_checks_failed?: string[]
  tests_passed?: number
  tests_failed?: number
  tests_run?: number
  status: FixStatus
  fix_branch?: string
  fix_commit_sha?: string
  fix_pr_number?: number
  fix_pr_url?: string
  is_verified: boolean
  verification_method?: string
  created_at: string
  applied_at?: string
}

// ── AI Provider ───────────────────────────────────────────────────────────────
export interface AIProvider {
  id: string
  name: string
  description: string
  type: 'local' | 'cloud_free' | 'cloud_paid'
  cost: string
  model: string
  default_model?: string
  models?: string[]
  available: boolean
  error?: string
  latency_ms?: number
  configured: boolean
  source?: 'provider' | 'personal' | 'none'
  category?: 'provider_models' | 'personal_models'
  priority_tag?: 'provider' | 'primary' | 'secondary'
  setup_url: string
  selected?: boolean
}

// ── Audit Log ─────────────────────────────────────────────────────────────────
export interface AuditLog {
  id: string
  actor_email?: string
  actor_role?: string
  action: string
  resource_type?: string
  resource_id?: string
  resource_name?: string
  details?: Record<string, any>
  result: 'success' | 'failure' | 'error'
  error_message?: string
  ip_address?: string
  created_at: string
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export interface FindingsSummary {
  total_open: number
  by_severity: Record<Severity, number>
  by_agent: Record<string, number>
  by_category: Array<{ category: string; count: number }>
}

export interface SystemHealth {
  overall: 'healthy' | 'degraded' | 'unhealthy'
  version: string
  environment: string
  checks: {
    database: { status: string; latency_ms: number }
    redis: { status: string; latency_ms: number }
    ai_providers: AIProvider[]
    scan_queue: { queued: number; running: number }
  }
  github_configured: boolean
  ai_providers_configured: string[]
}

// ── Tour ──────────────────────────────────────────────────────────────────────
export interface TourStep {
  id: string
  target: string
  title: string
  content: string
  position: 'top' | 'bottom' | 'left' | 'right'
}
