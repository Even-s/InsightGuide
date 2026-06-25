import { useState, useEffect } from 'react'

export type LayoutMode = 'compact' | 'standard' | 'wide' | 'ultrawide'
export type ContentOrientation = 'landscape' | 'portrait' | 'unknown'

export interface LayoutConfig {
  // 投影片區域
  contentArea: {
    width: string // Tailwind 類或百分比
    minWidth?: string
  }
  // 卡片區域
  cardsArea: {
    width: string
    height: string // flex-1 或固定高度
  }
  // 建議逐字稿區域
  scriptArea: {
    height: string
  }
  // 轉錄區域
  transcriptArea: {
    height: string
  }
  // 卡片佈局
  cardsLayout: {
    direction: 'horizontal' | 'vertical'
    cardWidth?: string // 僅用於水平佈局
    cardHeight: string
  }
}

/**
 * 動態響應式佈局 Hook
 * 根據視窗寬度、投影片方向自動調整佈局
 */
export function useResponsiveLayout(contentOrientation: ContentOrientation) {
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('standard')
  const [layoutConfig, setLayoutConfig] = useState<LayoutConfig>(getLayoutConfig('standard', contentOrientation))

  // 監聽視窗大小變化
  useEffect(() => {
    function updateLayoutMode() {
      const width = window.innerWidth

      if (width < 1280) {
        setLayoutMode('compact')
      } else if (width < 1536) {
        setLayoutMode('standard')
      } else if (width < 1920) {
        setLayoutMode('wide')
      } else {
        setLayoutMode('ultrawide')
      }
    }

    updateLayoutMode()
    window.addEventListener('resize', updateLayoutMode)

    return () => window.removeEventListener('resize', updateLayoutMode)
  }, [])

  // 當佈局模式或投影片方向改變時更新配置
  useEffect(() => {
    setLayoutConfig(getLayoutConfig(layoutMode, contentOrientation))
  }, [layoutMode, contentOrientation])

  return {
    layoutMode,
    layoutConfig,
    isCompact: layoutMode === 'compact',
    isWide: layoutMode === 'wide' || layoutMode === 'ultrawide',
  }
}

/**
 * 根據佈局模式和投影片方向獲取配置
 */
function getLayoutConfig(mode: LayoutMode, orientation: ContentOrientation): LayoutConfig {
  // 直立投影片的特殊處理
  if (orientation === 'portrait') {
    return getPortraitConfig(mode)
  }

  // 橫向投影片的配置
  switch (mode) {
    case 'compact':
      return {
        contentArea: {
          width: 'flex-1',
          minWidth: '640px',
        },
        cardsArea: {
          width: 'w-80',  // 320px
          height: 'min-h-0 flex-1',
        },
        scriptArea: {
          height: 'shrink-0',
        },
        transcriptArea: {
          height: 'h-16',  // 64px
        },
        cardsLayout: {
          direction: 'vertical',
          cardHeight: 'h-full',
        },
      }

    case 'standard':
      return {
        contentArea: {
          width: 'flex-1',
        },
        cardsArea: {
          width: 'w-96',  // 384px
          height: 'min-h-0 flex-1',
        },
        scriptArea: {
          height: 'shrink-0',
        },
        transcriptArea: {
          height: 'h-16',
        },
        cardsLayout: {
          direction: 'vertical',
          cardHeight: 'h-full',
        },
      }

    case 'wide':
      return {
        contentArea: {
          width: 'flex-[0_0_60%]',  // 60%
        },
        cardsArea: {
          width: 'w-[40%]',  // 40%
          height: 'min-h-0 flex-1',
        },
        scriptArea: {
          height: 'shrink-0',
        },
        transcriptArea: {
          height: 'h-20',  // 80px - 稍高
        },
        cardsLayout: {
          direction: 'vertical',
          cardHeight: 'h-full',
        },
      }

    case 'ultrawide':
      return {
        contentArea: {
          width: 'flex-[0_0_55%]',  // 55%
        },
        cardsArea: {
          width: 'w-[25%]',  // 25%
          height: 'min-h-0 flex-1',
        },
        scriptArea: {
          height: 'shrink-0',
        },
        transcriptArea: {
          height: 'h-24',  // 96px
        },
        cardsLayout: {
          direction: 'vertical',
          cardHeight: 'h-full',
        },
      }
  }
}

/**
 * 直立投影片的配置
 */
function getPortraitConfig(mode: LayoutMode): LayoutConfig {
  switch (mode) {
    case 'compact':
      return {
        contentArea: {
          width: 'flex-[0_0_45%]',  // 45%
        },
        cardsArea: {
          width: 'w-[55%]',  // 55%
          height: 'min-h-0 flex-1',
        },
        scriptArea: {
          height: 'shrink-0',
        },
        transcriptArea: {
          height: 'h-16',
        },
        cardsLayout: {
          direction: 'horizontal',
          cardWidth: 'w-56',  // 224px
          cardHeight: 'h-full',
        },
      }

    case 'standard':
      return {
        contentArea: {
          width: 'flex-[0_0_50%]',
        },
        cardsArea: {
          width: 'w-[50%]',
          height: 'min-h-0 flex-1',
        },
        scriptArea: {
          height: 'shrink-0',
        },
        transcriptArea: {
          height: 'h-16',
        },
        cardsLayout: {
          direction: 'horizontal',
          cardWidth: 'w-64',  // 256px
          cardHeight: 'h-full',
        },
      }

    case 'wide':
      return {
        contentArea: {
          width: 'flex-[0_0_50%]',
        },
        cardsArea: {
          width: 'w-[50%]',
          height: 'min-h-0 flex-1',
        },
        scriptArea: {
          height: 'shrink-0',
        },
        transcriptArea: {
          height: 'h-20',
        },
        cardsLayout: {
          direction: 'horizontal',
          cardWidth: 'w-72',  // 288px
          cardHeight: 'h-full',
        },
      }

    case 'ultrawide':
      return {
        contentArea: {
          width: 'flex-[0_0_45%]',
        },
        cardsArea: {
          width: 'w-[55%]',
          height: 'min-h-0 flex-1',
        },
        scriptArea: {
          height: 'shrink-0',
        },
        transcriptArea: {
          height: 'h-24',
        },
        cardsLayout: {
          direction: 'horizontal',
          cardWidth: 'w-80',  // 320px
          cardHeight: 'h-full',
        },
      }
  }
}
