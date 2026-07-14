import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import HomePage from './HomePage'

function renderHome() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/projects/new" element={<div>新建專案頁面</div>} />
        <Route path="/projects" element={<div>專案管理頁面</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('HomePage', () => {
  it('shows separate new-project and project-management entrances', () => {
    renderHome()

    expect(screen.getByRole('button', { name: '新建專案' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '管理專案' })).toBeInTheDocument()
  })

  it('opens the dedicated new-project page', () => {
    renderHome()

    fireEvent.click(screen.getByRole('button', { name: '新建專案' }))
    expect(screen.getByText('新建專案頁面')).toBeInTheDocument()
  })

  it('opens project management', () => {
    renderHome()

    fireEvent.click(screen.getByRole('button', { name: '管理專案' }))
    expect(screen.getByText('專案管理頁面')).toBeInTheDocument()
  })
})
