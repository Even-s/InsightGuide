/**
 * Project & Stakeholder API
 */

import { apiClient } from './client'

// --- Voice Input ---

export interface VoiceParseResult {
  transcript: string
  parsed: {
    title?: string | null
    description?: string | null
    business_domain?: string | null
    key_objectives?: string[]
    out_of_scope?: string[]
  }
}

export async function voiceToProjectFields(audioBlob: Blob): Promise<VoiceParseResult> {
  const formData = new FormData()
  formData.append('audio', audioBlob, 'recording.webm')
  const res = await apiClient.post('/api/projects/voice-to-project-fields', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export interface StakeholderSlotDraft {
  role_category: string
  role_label: string
  rationale: string
  expected_contributions: string[]
  key_questions_to_cover: string[]
  priority: string
  min_interviews: number
  first_wave: boolean
}

export interface StakeholderSlotDraftResult {
  transcript?: string | null
  draft: StakeholderSlotDraft
}

export async function voiceToStakeholderSlotDraft(
  projectId: string,
  audioBlob: Blob,
): Promise<StakeholderSlotDraftResult> {
  const formData = new FormData()
  formData.append('audio', audioBlob, 'role-description.webm')
  const res = await apiClient.post(
    `/api/projects/${projectId}/stakeholder-slot-draft/voice`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return res.data
}

export async function refineStakeholderSlotDraft(
  projectId: string,
  draft: StakeholderSlotDraft,
): Promise<StakeholderSlotDraftResult> {
  const res = await apiClient.post(
    `/api/projects/${projectId}/stakeholder-slot-draft/refine`,
    draft,
  )
  return res.data
}

export interface StakeholderProfileDraft {
  name: string
  role_title: string
  department: string
  stakeholder_type: string
  expertise_tags: string[]
  knowledge_boundaries: string[]
}

export interface StakeholderProfileDraftResult {
  transcript?: string | null
  draft: StakeholderProfileDraft
}

export async function voiceToStakeholderProfileDraft(
  projectId: string,
  slotId: string,
  audioBlob: Blob,
): Promise<StakeholderProfileDraftResult> {
  const formData = new FormData()
  formData.append('audio', audioBlob, 'participant-description.webm')
  const res = await apiClient.post(
    `/api/projects/${projectId}/stakeholder-profile-draft/voice`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { slot_id: slotId },
    },
  )
  return res.data
}

// --- Types ---

export interface Project {
  id: string
  userId: string
  title: string
  description?: string
  status: string
  mode: 'formal' | 'demo'
  isEphemeral: boolean
  expiresAt?: string | null
  templateId?: string | null
  createdAt: string
  updatedAt: string
}

export interface StakeholderSlot {
  id: string
  projectId: string
  roleCategory: string
  roleLabel: string
  rationale?: string
  expectedContributions: string[]
  keyQuestionsToCover: string[]
  priority: string
  minInterviews: number
  firstWave: boolean
  status: string
  orderIndex: number
  source: string
  profilesCount: number
  interviewsDone: number
  createdAt: string
  updatedAt: string
}

export interface StakeholderProfile {
  id: string
  projectId: string
  assignedSlotIds: string[]
  primarySlotId?: string | null
  name: string
  roleTitle?: string
  department?: string
  stakeholderType: string
  expertiseTags: string[]
  knowledgeBoundaries: string[]
  decisionPower?: string
  status: string
  interviewCount: number
  lastInterviewedAt?: string
  recommendedByMemoId?: string
  recommendedReason?: string
  notes?: string
  createdAt: string
  updatedAt: string
}

export interface StakeholderPlan {
  slots: StakeholderSlot[]
  profiles: StakeholderProfile[]
  summary: {
    total_slots: number
    completed_slots: number
    progress_percentage: number
    first_wave_total: number
    first_wave_completed: number
    generation_source: 'ai_suggested' | 'fallback' | 'user_created'
    slots: Array<{
      id: string
      role_label: string
      role_category: string
      priority: string
      first_wave: boolean
      status: string
      profiles_count: number
      min_interviews: number
      interviews_done: number
    }>
    next_recommended_action?: {
      action: string
      target_role: string
      role_category: string
      reason: string
    }
  }
}

export interface ProjectDashboard {
  project: Project
  stakeholderPlan: StakeholderPlan['summary']
  interviewProgress: {
    total_sessions: number
    completed_sessions: number
    total_profiles: number
    interviewed_profiles: number
  }
  nextAction?: {
    action: string
    target_role: string
    role_category: string
    reason: string
  }
}

// --- Project API ---

export async function createProject(data: {
  title: string
  description?: string
}): Promise<Project> {
  const res = await apiClient.post('/api/projects', data)
  return res.data
}

export async function listProjects(): Promise<{ projects: Project[]; total: number }> {
  const res = await apiClient.get('/api/projects')
  return res.data
}

export async function getProject(projectId: string): Promise<Project> {
  const res = await apiClient.get(`/api/projects/${projectId}`)
  return res.data
}

export async function getProjectDashboard(projectId: string): Promise<ProjectDashboard> {
  const res = await apiClient.get(`/api/projects/${projectId}/dashboard`)
  return res.data
}

export async function updateProject(projectId: string, data: {
  title?: string
  description?: string
  status?: string
}): Promise<Project> {
  const res = await apiClient.put(`/api/projects/${projectId}`, data)
  return res.data
}

export async function deleteProject(projectId: string): Promise<void> {
  await apiClient.delete(`/api/projects/${projectId}`)
}

// --- Stakeholder Plan API ---

export async function getStakeholderPlan(projectId: string): Promise<StakeholderPlan> {
  const res = await apiClient.get(`/api/projects/${projectId}/stakeholder-plan`)
  return res.data
}

export async function regenerateStakeholderPlan(projectId: string): Promise<{ slots: StakeholderSlot[] }> {
  const res = await apiClient.post(`/api/projects/${projectId}/stakeholder-plan/regenerate`)
  return res.data
}

export async function createStakeholderSlot(projectId: string, data: {
  role_category: string
  role_label: string
  rationale?: string
  expected_contributions?: string[]
  key_questions_to_cover?: string[]
  priority?: string
  min_interviews?: number
  first_wave?: boolean
}): Promise<StakeholderSlot> {
  const res = await apiClient.post(`/api/projects/${projectId}/stakeholder-slots`, data)
  return res.data
}

export async function updateStakeholderSlot(slotId: string, data: {
  role_category?: string
  role_label?: string
  rationale?: string
  expected_contributions?: string[]
  key_questions_to_cover?: string[]
  priority?: string
  min_interviews?: number
  first_wave?: boolean
  status?: string
}): Promise<StakeholderSlot> {
  const res = await apiClient.put(`/api/projects/stakeholder-slots/${slotId}`, data)
  return res.data
}

export async function skipStakeholderSlot(slotId: string): Promise<StakeholderSlot> {
  const res = await apiClient.put(`/api/projects/stakeholder-slots/${slotId}/skip`)
  return res.data
}

export async function unskipStakeholderSlot(slotId: string): Promise<StakeholderSlot> {
  const res = await apiClient.put(`/api/projects/stakeholder-slots/${slotId}/unskip`)
  return res.data
}

export async function reorderStakeholderSlots(slotIds: string[]): Promise<void> {
  await apiClient.put('/api/projects/stakeholder-slots/reorder', { slot_ids: slotIds })
}

export async function deleteStakeholderSlot(slotId: string): Promise<void> {
  await apiClient.delete(`/api/projects/stakeholder-slots/${slotId}`)
}

// --- Stakeholder Profile API ---

export async function createStakeholder(projectId: string, data: {
  slot_ids?: string[]
  primary_slot_id?: string | null
  name: string
  role_title?: string
  department?: string
  stakeholder_type: string
  expertise_tags?: string[]
  knowledge_boundaries?: string[]
  decision_power?: string
  notes?: string
}): Promise<StakeholderProfile> {
  const res = await apiClient.post(`/api/projects/${projectId}/stakeholders`, data)
  return res.data
}

export async function listStakeholders(projectId: string): Promise<StakeholderProfile[]> {
  const res = await apiClient.get(`/api/projects/${projectId}/stakeholders`)
  return res.data
}

export async function updateStakeholder(profileId: string, data: {
  name?: string
  stakeholder_type?: string
  expertise_tags?: string[]
  knowledge_boundaries?: string[]
  status?: string
}): Promise<StakeholderProfile> {
  const res = await apiClient.put(`/api/projects/stakeholders/${profileId}`, data)
  return res.data
}

export async function updateStakeholderProfileSlots(profileId: string, data: {
  slot_ids: string[]
  primary_slot_id?: string | null
}): Promise<StakeholderProfile> {
  const res = await apiClient.put(`/api/projects/stakeholders/${profileId}/slots`, data)
  return res.data
}

export async function cancelStakeholder(profileId: string): Promise<StakeholderProfile> {
  const res = await apiClient.put(`/api/projects/stakeholders/${profileId}/cancel`)
  return res.data
}

export async function deleteStakeholder(profileId: string): Promise<void> {
  await apiClient.delete(`/api/projects/stakeholders/${profileId}`)
}

// --- Interview Brief API ---

export interface InterviewBrief {
  id: string
  sessionId: string
  stakeholderProfileId: string
  projectId: string
  interviewObjective: string
  recommendedTopics: Array<{ topic: string; reason: string; priority: string }>
  excludedTopics: Array<{ topic: string; reason: string }>
  suggestedQuestions: Array<{ question: string; intent: string; expected_insight: string }>
  followUpFromPriorInterviews: Array<{ question: string; origin_memo_id?: string; origin_stakeholder?: string; reason?: string }>
  applicableCardIds: string[]
  notApplicableCards: Array<{ card_id: string; question: string; target_roles: string[] }>
  timeEstimateMinutes?: number
  notes?: string
  generatedAt?: string
}

export async function generateInterviewBrief(sessionId: string): Promise<InterviewBrief> {
  const res = await apiClient.post(`/api/interview-sessions/${sessionId}/brief`)
  return res.data
}

export async function getInterviewBrief(sessionId: string): Promise<InterviewBrief> {
  const res = await apiClient.get(`/api/interview-sessions/${sessionId}/brief`)
  return res.data
}

// --- Insight Memo API ---

export interface InsightMemo {
  id: string
  sessionId: string
  projectId?: string
  stakeholderProfileId?: string
  interviewSeriesId?: string
  interviewRoundId?: string
  interviewDate?: string
  interviewDurationMinutes?: number
  topicsCovered: string[]
  stakeholderSummary?: {
    name: string
    role: string
    department?: string
    expertise: string[]
    boundaries: string[]
  }
  questionSummaries: Array<{
    question: string
    summary: string
    status: string
    confidence?: number
  }>
  painPoints: Array<{
    description: string
    evidence_quote: string
    affected_roles: string[]
    severity: string
  }>
  requirementCandidates: Array<{
    description: string
    source: string
    confidence: string
    evidence_quote: string
    needs_validation_from: string[]
    brd_ready: boolean
  }>
  constraintsAndAssumptions: Array<{
    type: string
    content: string
    source: string
    evidence_quote: string
  }>
  processDescriptions: Array<{
    process_name: string
    steps: string[]
    pain_points: string[]
    source_quote: string
  }>
  unresolvedQuestions: Array<{
    question: string
    suggested_stakeholder_type: string
    priority: string
    reason: string
  }>
  nextInterviewSuggestions: Array<{
    target_role: string
    objective: string
    key_questions: string[]
  }>
  sourceDistinction?: {
    explicit_statements: number
    inferences: number
    unverified: number
  }
  markdownContent?: string
  status: string
  generatedAt?: string
  createdAt?: string
}

export async function generateInsightMemo(sessionId: string): Promise<InsightMemo> {
  const res = await apiClient.post(`/api/sessions/${sessionId}/insight-memo`)
  return res.data
}

export async function getInsightMemo(sessionId: string): Promise<InsightMemo> {
  const res = await apiClient.get(`/api/sessions/${sessionId}/insight-memo`)
  return res.data
}

export async function listProjectInsightMemos(projectId: string): Promise<{ memos: InsightMemo[]; total: number }> {
  const res = await apiClient.get(`/api/projects/${projectId}/insight-memos`)
  return res.data
}

// --- Evidence Matrix API ---

export interface DerivedEvidenceRequirement {
  id: string
  matrixId: string
  source?: 'round_aggregate'
  editable?: boolean
  requirementCandidate: string
  category?: string
  sourceRoles: string[]
  sourceMemoIds: string[]
  supportingEvidence: Array<{
    memo_id: string
    stakeholder_role: string
    stakeholder_name: string
    evidence_quote: string
    source_type: string
    confidence: string
  }>
  conflicts: Array<{ description: string; conflicting_roles: string[]; details: string }>
  validationStatus: string
  missingValidationFrom: string[]
  mentionCount: number
  stakeholderAgreementLevel?: string
  createdAt?: string
  updatedAt?: string
}

export interface EvidenceMatrixResponse {
  matrix: {
    id: string
    projectId: string
    status: string
    source?: 'round_aggregate'
    editable?: boolean
    memoCount: number
    lastUpdatedAt?: string
    markdownContent?: string
  } | null
  entries: DerivedEvidenceRequirement[]
  summary: {
    total_candidates: number
    validated: number
    conflicted: number
    needs_more_evidence: number
    candidate: number
    roles_heard_from: string[]
    roles_missing: string[]
    memo_count: number
    status: string
    last_updated_at?: string
  }
}

export async function getEvidenceMatrix(projectId: string): Promise<EvidenceMatrixResponse> {
  const res = await apiClient.get(`/api/projects/${projectId}/evidence-matrix`)
  return res.data
}

export async function refreshEvidenceMatrix(projectId: string): Promise<EvidenceMatrixResponse> {
  const res = await apiClient.post(`/api/projects/${projectId}/evidence-matrix/refresh`)
  return res.data
}

export async function getInterviewSuggestions(projectId: string): Promise<{
  suggestions: Array<{ target_role: string; reason: string; urgency: string }>
  summary: EvidenceMatrixResponse['summary']
}> {
  const res = await apiClient.get(`/api/projects/${projectId}/interview-suggestions`)
  return res.data
}

// --- BRD Readiness API ---

export interface BRDReadinessReport {
  id: string
  projectId: string
  isReady: boolean
  readinessScore?: number
  generationMode?: string
  recommendation?: string
  readyChapters: Array<{
    chapter: string
    evidence_count: number
    source_roles: string[]
    confidence: string
  }>
  insufficientChapters: Array<{
    chapter: string
    reason: string
    missing_roles: string[]
    priority: string
  }>
  unresolvedConflicts: Array<{
    topic: string
    conflicting_parties: string[]
    details: string
  }>
  suggestedNextInterviews: Array<{
    target_role: string
    role_category?: string
    objective: string
    urgency: string
    key_questions: string[]
  }>
  stakeholderCoverage?: {
    required_roles_total: number
    required_roles_covered: number
    skipped_roles: string[]
    missing_roles: string[]
    coverage_percentage: number
  }
  totalMemos: number
  totalStakeholdersInterviewed: number
  totalEvidenceEntries: number
  validatedRequirements: number
  markdownContent?: string
  generatedAt?: string
}

export async function generateReadinessReport(projectId: string): Promise<BRDReadinessReport> {
  const res = await apiClient.post(`/api/projects/${projectId}/readiness-check`)
  return res.data
}

export async function getReadinessReport(projectId: string): Promise<BRDReadinessReport> {
  const res = await apiClient.get(`/api/projects/${projectId}/readiness-report`)
  return res.data
}

export async function generateProjectBRD(projectId: string): Promise<{
  status: string
  readinessReport?: BRDReadinessReport
  message: string
  canGenerate?: boolean
}> {
  const res = await apiClient.post(`/api/projects/${projectId}/generate-brd`)
  return res.data
}

// --- Stakeholder Interview Guide API ---

export interface InterviewGuide {
  document_id: string
  prep_session_id: string
  interview_round_id?: string
  guide_version?: number
  is_frozen?: boolean
  themes: Array<{
    id: string
    theme_number: number
    title: string
    rationale?: string
    priority?: number
    estimated_minutes?: number
    card_count?: number
  }>
  card_count: number
  status: string
}

export interface InterviewGuideOptions {
  duration_minutes?: number
  interview_purpose?: string
  focus_topics?: string
  exclude_topics?: string
  interview_style?: string
  target_card_count?: number
  must_cover_topics?: string[]
  reference_questions?: string[]
}

export interface InterviewGuideDraft {
  duration_minutes: number
  interview_purpose: string
  focus_topics: string
  exclude_topics: string
  interview_style: string
}

export interface InterviewGuideDraftResult {
  transcript?: string | null
  draft: InterviewGuideDraft
}

export async function voiceToInterviewGuideDraft(
  projectId: string,
  profileId: string,
  audioBlob: Blob,
  currentOptions: InterviewGuideDraft,
): Promise<InterviewGuideDraftResult> {
  const formData = new FormData()
  formData.append('audio', audioBlob, 'guide-settings.webm')
  formData.append('current_options', JSON.stringify(currentOptions))
  const res = await apiClient.post(
    `/api/projects/${projectId}/stakeholders/${profileId}/interview-guide-draft/voice`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return res.data
}

export async function generateInterviewGuide(
  projectId: string,
  profileId: string,
  options?: InterviewGuideOptions,
): Promise<InterviewGuide> {
  const res = await apiClient.post(
    `/api/projects/${projectId}/stakeholders/${profileId}/generate-interview-guide`,
    options || {}
  )
  return res.data
}

export async function getInterviewGuide(
  projectId: string,
  profileId: string
): Promise<InterviewGuide> {
  const res = await apiClient.get(
    `/api/projects/${projectId}/stakeholders/${profileId}/interview-guide`
  )
  return res.data
}
