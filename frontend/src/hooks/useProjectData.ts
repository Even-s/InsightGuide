import { useCallback, useEffect, useState } from 'react'
import {
  getProjectDashboard,
  getStakeholderPlan,
  getInterviewGuide,
  type ProjectDashboard,
  type StakeholderPlan,
  type InterviewGuide,
} from '@/api/projects'

export function useProjectData(projectId: string | undefined) {
  const [dashboard, setDashboard] = useState<ProjectDashboard | null>(null)
  const [plan, setPlan] = useState<StakeholderPlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [guideStatuses, setGuideStatuses] = useState<Record<string, InterviewGuide | null>>({})

  const loadData = useCallback(async () => {
    if (!projectId) return
    try {
      setLoading(true)
      const [dashData, planData] = await Promise.all([
        getProjectDashboard(projectId),
        getStakeholderPlan(projectId),
      ])
      setDashboard(dashData)
      setPlan(planData)

      const statuses: Record<string, InterviewGuide | null> = {}
      for (const profile of planData.profiles) {
        try {
          const guide = await getInterviewGuide(projectId, profile.id)
          statuses[profile.id] = guide
        } catch {
          statuses[profile.id] = null
        }
      }
      setGuideStatuses(statuses)
    } catch (err) {
      console.error('Failed to load project:', err)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => { loadData() }, [loadData])

  return { dashboard, plan, loading, guideStatuses, setGuideStatuses, loadData }
}
