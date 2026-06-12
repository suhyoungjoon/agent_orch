"use client";

/**
 * 공통 UX 프리미티브 — 로딩·에러·빈 상태를 일관되게 표현하기 위한 공유 컴포넌트.
 * 모든 목록/데이터 화면에서 import해서 사용한다.
 */

import { AlertCircle } from "lucide-react";

// ── 에러 배너 ─────────────────────────────────────────────────────────

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 flex items-start gap-3">
      <AlertCircle size={15} className="text-red-500 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-red-700">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-1 text-xs text-red-600 hover:text-red-700 underline underline-offset-2"
          >
            다시 시도
          </button>
        )}
      </div>
    </div>
  );
}

// ── 빈 상태 ───────────────────────────────────────────────────────────

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: React.ElementType;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-gray-200 py-16 flex flex-col items-center text-center px-4">
      {Icon && <Icon size={36} className="mb-3 text-gray-200" />}
      <p className="text-sm font-semibold text-gray-500">{title}</p>
      {description && (
        <p className="text-xs text-gray-400 mt-1 max-w-xs">{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

// ── 테이블 행 스켈레톤 (감사 로그, A2A 체인 등) ─────────────────────

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 px-4 py-3 rounded-xl bg-gray-50"
        >
          <div className="w-24 h-3 rounded bg-gray-200" />
          <div className="flex-1 h-3 rounded bg-gray-200" />
          <div className="w-20 h-3 rounded bg-gray-200" />
          <div className="w-16 h-5 rounded-full bg-gray-200" />
        </div>
      ))}
    </div>
  );
}

// ── 카드 그리드 스켈레톤 (에이전트, MCP 서버, 이상 탐지 등) ─────────

export function CardGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-gray-100 bg-white p-4 space-y-3"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-200 shrink-0" />
            <div className="flex-1 h-4 rounded bg-gray-200" />
            <div className="w-14 h-5 rounded-full bg-gray-100" />
          </div>
          <div className="h-3 w-3/4 rounded bg-gray-100" />
          <div className="h-3 w-1/2 rounded bg-gray-100" />
        </div>
      ))}
    </div>
  );
}

// ── 지표 카드 스켈레톤 (ROI, 대시보드 요약 등) ───────────────────────

export function MetricSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div
      className={`grid gap-4 animate-pulse grid-cols-2 sm:grid-cols-${Math.min(count, 4)}`}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-gray-100 bg-white p-4 space-y-2"
        >
          <div className="h-3 w-16 rounded bg-gray-200" />
          <div className="h-7 w-24 rounded bg-gray-200" />
          <div className="h-3 w-20 rounded bg-gray-100" />
        </div>
      ))}
    </div>
  );
}

// ── 에이전트 카드 스켈레톤 (TeamRegistry 전용) ───────────────────────

export function AgentCardSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-gray-100 bg-white p-4 space-y-3"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-1.5 flex-1">
              <div className="h-4 w-32 rounded bg-gray-200" />
              <div className="h-3 w-full rounded bg-gray-100" />
            </div>
            <div className="w-16 h-5 rounded-full bg-gray-200 shrink-0" />
          </div>
          <div className="flex gap-1.5">
            <div className="h-5 w-12 rounded bg-gray-100" />
            <div className="h-5 w-14 rounded bg-gray-100" />
          </div>
          <div className="flex items-center justify-between pt-1">
            <div className="h-3 w-20 rounded bg-gray-100" />
            <div className="h-6 w-16 rounded-lg bg-gray-200" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── 인라인 스피너 (버튼 내부 등 소형 용도) ──────────────────────────

export function InlineSpinner({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`animate-spin h-4 w-4 ${className}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12" cy="12" r="10"
        stroke="currentColor" strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
