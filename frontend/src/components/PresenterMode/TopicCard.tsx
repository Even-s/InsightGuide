import { useState, useRef } from 'react';
import clsx from 'clsx';
import type { CardState } from '@/types/presentation';
import type { CardImportance, CardStatus, QuestionCard as TopicCardType } from '@/types/questionCard';
import Badge from '@/components/common/Badge';
import { formatFocusText, formatQuestionText } from '@/utils/interviewCopy';

interface TopicCardProps {
  cardState?: CardState;
  card?: TopicCardType;
  animated?: boolean;
  cardHeight?: string;  // 動態高度，如 h-64
  onMarkStatus?: (cardState: CardState, status: CardStatus) => void;
}

interface ImportantPoint {
  id: string;
  text: string;
  fallbackIds: string[];
}

export default function TopicCard({ cardState, card, animated = true, cardHeight = 'h-44', onMarkStatus }: TopicCardProps) {
  const [swipeX, setSwipeX] = useState(0);
  const [isSwiping, setIsSwiping] = useState(false);
  const [hasMovedRef, setHasMovedRef] = useState(false);
  const startXRef = useRef(0);
  const startYRef = useRef(0);
  const questionCard = cardState?.questionCard ?? card;

  if (!questionCard) return null;

  const status = cardState?.status ?? questionCard.status;
  const { importance, focusText, questionText, coverageRule } = questionCard;
  const title = formatFocusText(focusText) || formatQuestionText(questionText);
  const evidence = cardState?.evidence ?? questionCard.evidence ?? null;
  const coveredAspectIds = getStringSet(evidence, 'coveredAspectIds');
  const importantPoints = getImportantPoints(coverageRule);
  const hasTalkingPoints = importantPoints.length > 0;
  const talkingPointIds = importantPoints.map((point) => point.id);
  const coveredTalkingPointCount = importantPoints.filter((point) => (
    isTalkingPointCovered(point.id, coveredAspectIds, point.fallbackIds)
  )).length;
  const aspectProgress = talkingPointIds.length > 0 ? coveredTalkingPointCount / talkingPointIds.length : null;
  const confidence = aspectProgress ?? cardState?.confidence ?? questionCard.confidence;
  const isCompleted = isCompletedStatus(status);
  const displayConfidence = confidence ?? (isCompleted ? 1 : 0);
  const waterLevel = Math.max(0, Math.min(100, displayConfidence * 100));

  const cardStyles = getCardStyles(status, importance);
  const StatusIcon = getStatusIcon(status);

  // 判斷是否正在講這張卡片（listening 狀態且有進度）
  const isActivelyPresenting = status === 'listening' && confidence !== undefined && confidence !== null && confidence > 0;
  // 判斷是否剛開始講（listening 但還沒進度）
  const isJustStarted = status === 'listening' && (confidence === undefined || confidence === null || confidence === 0);

  // Handle touch/mouse swipe for reset (horizontal only)
  function handleSwipeStart(e: React.TouchEvent | React.MouseEvent) {
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    startXRef.current = clientX;
    startYRef.current = clientY;
    setIsSwiping(true);
    setHasMovedRef(false);
  }

  function handleSwipeMove(e: React.TouchEvent | React.MouseEvent) {
    if (!isSwiping) return;
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

    const diffX = clientX - startXRef.current;
    const diffY = Math.abs(clientY - startYRef.current);

    // Mark that user has moved
    if (Math.abs(diffX) > 5 || diffY > 5) {
      setHasMovedRef(true);
    }

    // Only swipe if horizontal movement is dominant
    if (diffY < 10) {
      // Calculate new position, clamped between -80 and 0
      const newX = Math.max(Math.min(diffX, 0), -80);
      setSwipeX(newX);
    }
  }

  function handleSwipeEnd() {
    setIsSwiping(false);
    if (swipeX < -40) {
      setSwipeX(-80);
    } else {
      setSwipeX(0);
    }
  }

  // Click card to close reset button (only if not swiping)
  function handleCardClick(e: React.MouseEvent) {
    // Ignore if it was a swipe/drag movement
    if (hasMovedRef) {
      setHasMovedRef(false);
      return;
    }

    // Only close reset button on actual click
    if (swipeX < 0) {
      e.stopPropagation();
      setSwipeX(0);
    }
  }

  function handleReset() {
    if (cardState && onMarkStatus) {
      onMarkStatus(cardState, 'pending');
      setSwipeX(0);
    }
  }

  return (
    <div className="relative h-full overflow-hidden">
      {/* Reset button (revealed on swipe) */}
      <div
        className="absolute right-0 top-0 flex h-full w-20 items-center justify-center bg-gray-500"
        style={{ transform: `translateX(${swipeX + 80}px)` }}
      >
        <button
          type="button"
          onClick={handleReset}
          className="flex flex-col items-center gap-1 text-white"
          aria-label="重置卡片狀態"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span className="text-xs">重置</span>
        </button>
      </div>

      {/* Main card content */}
      <div
        className={clsx(
          'rounded-lg p-3 transition-all duration-300 relative overflow-hidden',
          `${cardHeight} flex flex-col`,  // 動態高度
          // 背景：有進度時用白色，無進度時用狀態色
          displayConfidence > 0 ? 'bg-white' : cardStyles.bg,
          // 邊框：統一寬度，只改變顏色
          'border',
          displayConfidence > 0
            ? (isCompleted ? 'border-sage-300' : 'border-sage-200')
            : cardStyles.border,
          animated && cardStyles.animation,
          // 正在講時突出顯示 - 使用陰影和顏色，但邊框保持單一寬度
          isActivelyPresenting && 'shadow-natural-lg border-sage-400',
          isJustStarted && 'shadow-natural border-sage-300'
        )}
        style={{ transform: `translateX(${swipeX}px)`, transition: isSwiping ? 'none' : 'transform 0.2s ease-out' }}
        onTouchStart={handleSwipeStart}
        onTouchMove={handleSwipeMove}
        onTouchEnd={handleSwipeEnd}
        onMouseDown={handleSwipeStart}
        onMouseMove={handleSwipeMove}
        onMouseUp={handleSwipeEnd}
        onMouseLeave={handleSwipeEnd}
        onClick={handleCardClick}
      >
        {/* 進度覆蓋層 - 從底部上升 */}
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 z-0 overflow-hidden rounded-b-lg transition-[height,opacity] duration-[1200ms] ease-out"
          style={{
            opacity: waterLevel > 0 ? 1 : 0,
            height: `${waterLevel}%`,
          }}
          aria-hidden="true"
        >
            {/* 水體背景 */}
            <div
              className={clsx(
                'absolute inset-0',
                isCompleted
                  ? 'bg-sage-200/45'
                  : 'bg-sage-100/55'
              )}
            />

        </div>

        {/* 內容層 - 在水位之上 */}
        <div className="relative z-10 flex flex-col h-full">
      {/* 卡片標題列 */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          {StatusIcon && <StatusIcon className={clsx('mt-0.5 h-5 w-5 shrink-0', cardStyles.icon)} />}
          <h3 className={clsx(
            'min-w-0 break-words text-lg font-bold leading-relaxed tracking-wide',
            isCompleted ? 'text-natural-400 line-through' : 'text-natural-700'
          )}>
            {title}
          </h3>
        </div>
        <ImportanceBadge importance={importance} />
      </div>

      {/* 演講重點 */}
      {hasTalkingPoints && (
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <ul className="space-y-2">
            {importantPoints.map((point) => (
              <TalkingPointItem
                key={point.id}
                text={point.text}
                marker="✓"
                status={status}
                isActive={isActivelyPresenting || isJustStarted}
                isCovered={isTalkingPointCovered(point.id, coveredAspectIds, point.fallbackIds)}
                emphasized
              />
            ))}
          </ul>
        </div>
      )}

      {/* 空白填充（當沒有演講重點時） */}
      {!hasTalkingPoints && (
        <div className="flex-1 min-h-0" />
      )}

        </div>
      </div>
    </div>
  );
}

function getImportantPoints(coverageRule: TopicCardType['coverageRule']): ImportantPoint[] {
  const facts = (coverageRule.mustMentionElements ?? []).slice(0, 3);
  if (facts.length > 0) {
    return facts
      .map((fact, index) => ({
        id: `fact_${index}`,
        text: formatFocusText(fact.text),
        fallbackIds: [`anchor_${index}`],
      }))
      .filter((point): point is ImportantPoint => Boolean(point.text));
  }

  return (coverageRule.semanticAnchors ?? []).slice(0, 3)
    .map((anchor, index) => ({
      id: `anchor_${index}`,
      text: formatFocusText(anchor),
      fallbackIds: [] as string[],
    }))
    .filter((point): point is ImportantPoint => Boolean(point.text));
}

function getStringSet(evidence: unknown, key: string) {
  const values = new Set<string>();
  if (!evidence || typeof evidence !== 'object') return values;
  const evidenceRecord = evidence as Record<string, unknown>;

  const rawValue = evidenceRecord[key];
  if (!Array.isArray(rawValue)) return values;

  rawValue.forEach((item) => {
    if (typeof item === 'string' && item.trim()) {
      values.add(normalizeText(item));
    }
  });

  return values;
}

function normalizeText(value: string) {
  return value.replace(/\s+/g, '').replace(/[，。、；：:,.!！?？「」『』（）()]/g, '').toLowerCase();
}

function isTalkingPointCovered(
  id: string,
  coveredAspectIds: Set<string>,
  fallbackIds: string[] = [],
) {
  if (coveredAspectIds.has(normalizeText(id))) return true;
  if (fallbackIds.some((fallbackId) => coveredAspectIds.has(normalizeText(fallbackId)))) return true;
  return false;
}

function TalkingPointItem({
  text,
  marker,
  status,
  isActive,
  isCovered,
  emphasized = false,
}: {
  text: string;
  marker: string;
  status: CardStatus;
  isActive: boolean;
  isCovered: boolean;
  emphasized?: boolean;
}) {
  return (
    <li className={clsx(
      'flex items-start gap-2 text-base leading-relaxed',
      emphasized && 'font-medium',
      isCovered
        ? 'text-natural-400 line-through decoration-sage-500 decoration-2'
        : isCompletedStatus(status)
          ? 'text-natural-500'
          : isActive
            ? 'text-natural-700 font-medium'
            : 'text-natural-600'
    )}>
      <span className={clsx(
        'shrink-0 text-lg leading-relaxed',
        isCovered
          ? 'text-sage-500'
          : isCompletedStatus(status)
            ? 'text-sage-500'
            : isActive
              ? 'text-sage-400'
              : 'text-natural-300'
      )}>
        {marker}
      </span>
      <span className="min-w-0 break-words">{text}</span>
    </li>
  );
}


function getCardStyles(status: CardStatus, importance: CardImportance) {
  const styles = {
    bg: '',
    border: '',
    animation: '',
    icon: ''
  };

  switch (status) {
    case 'listening':
      styles.bg = 'bg-yellow-50';
      styles.border = 'border-yellow-200';
      styles.animation = 'animate-pulse';
      styles.icon = 'text-yellow-500';
      break;
    case 'sufficient':
    case 'covered':
      styles.bg = 'bg-sage-50';
      styles.border = 'border-sage-200';
      styles.icon = 'text-sage-500';
      break;
    case 'probably_sufficient':
    case 'probably_covered':
      styles.bg = 'bg-wood-50';
      styles.border = 'border-wood-200';
      styles.icon = 'text-wood-400';
      break;
    case 'at_risk':
      styles.bg = 'bg-cream-200';
      styles.border = 'border-wood-300';
      styles.animation = 'animate-pulse';
      styles.icon = 'text-wood-500';
      break;
    case 'skipped':
      styles.bg = 'bg-cream-100';
      styles.border = 'border-cream-300';
      styles.icon = 'text-natural-400';
      break;
    default:
      styles.bg = 'bg-cream-50';
      styles.border = importance === 'must'
        ? 'border-sage-200'
        : 'border-cream-300';
  }

  return styles;
}

function getStatusIcon(status: CardStatus) {
  switch (status) {
    case 'sufficient':
    case 'covered':
      return CheckCircleIcon;
    case 'probably_sufficient':
    case 'probably_covered':
      return CheckIcon;
    case 'at_risk':
      return AlertTriangleIcon;
    case 'skipped':
      return XCircleIcon;
    default:
      return null;
  }
}

function isCompletedStatus(status: CardStatus) {
  return status === 'sufficient' || status === 'covered' || status === 'manually_checked';
}

function ImportanceBadge({ importance }: { importance: CardImportance }) {
  const labels = {
    must: '必講',
    should: '選講',
    optional: '選填'
  };

  const tones = {
    must: 'red',
    should: 'blue',
    optional: 'gray'
  } as const;

  return (
    <Badge tone={tones[importance]}>
      {labels[importance]}
    </Badge>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.53-9.47a.75.75 0 00-1.06-1.06L9 10.94 7.53 9.47a.75.75 0 00-1.06 1.06l2 2a.75.75 0 001.06 0l4-4z" clipRule="evenodd" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

function AlertTriangleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 10l4 4m0-4l-4 4m11-2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
