import { useState } from 'react'
import { createStakeholder } from '@/api/projects'

const STAKEHOLDER_TYPES = [
  { value: 'business', label: '業務' },
  { value: 'product', label: '產品' },
  { value: 'engineering', label: '工程' },
  { value: 'management', label: '管理' },
  { value: 'operations', label: '維運' },
  { value: 'customer_support', label: '客服' },
  { value: 'legal', label: '法務' },
  { value: 'finance', label: '財務' },
  { value: 'design', label: '設計' },
  { value: 'qa', label: '品保' },
  { value: 'other', label: '其他' },
]

interface AddProfileModalProps {
  slotId: string
  projectId: string
  onClose: () => void
  onAdd: () => void
}

export function AddProfileModal({ slotId, projectId, onClose, onAdd }: AddProfileModalProps) {
  const [profileName, setProfileName] = useState('')
  const [profileRole, setProfileRole] = useState('')
  const [profileType, setProfileType] = useState('business')
  const [profileDept, setProfileDept] = useState('')
  const [profileExpertise, setProfileExpertise] = useState('')
  const [profileBoundaries, setProfileBoundaries] = useState('')

  const handleAddProfile = async () => {
    if (!projectId || !profileName.trim()) return
    try {
      await createStakeholder(projectId, {
        slot_id: slotId || undefined,
        name: profileName.trim(),
        role_title: profileRole.trim() || undefined,
        department: profileDept.trim() || undefined,
        stakeholder_type: profileType,
        expertise_tags: profileExpertise.split(',').map(s => s.trim()).filter(Boolean),
        knowledge_boundaries: profileBoundaries.split(',').map(s => s.trim()).filter(Boolean),
      })
      onAdd()
    } catch (err) {
      console.error('Failed to create stakeholder:', err)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-natural" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-natural-800 mb-4">新增受訪者</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">姓名 *</label>
            <input
              type="text"
              value={profileName}
              onChange={e => setProfileName(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="受訪者姓名"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">職稱</label>
            <input
              type="text"
              value={profileRole}
              onChange={e => setProfileRole(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="例：資深業務經理"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">部門</label>
            <input
              type="text"
              value={profileDept}
              onChange={e => setProfileDept(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="例：業務部"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">角色類型</label>
            <select
              value={profileType}
              onChange={e => setProfileType(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
            >
              {STAKEHOLDER_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">
              專長領域（逗號分隔）
            </label>
            <input
              type="text"
              value={profileExpertise}
              onChange={e => setProfileExpertise(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="sales_process, customer_pain_points, pricing"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">
              不熟悉領域（逗號分隔）
            </label>
            <input
              type="text"
              value={profileBoundaries}
              onChange={e => setProfileBoundaries(e.target.value)}
              className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
              placeholder="technical_architecture, database, deployment"
            />
          </div>
        </div>
        <div className="flex gap-3 mt-5">
          <button
            onClick={handleAddProfile}
            disabled={!profileName.trim()}
            className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 disabled:opacity-50"
          >
            新增
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-cream-100 text-natural-700 rounded-lg hover:bg-cream-200"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
