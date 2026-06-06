"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, LayoutDashboard, Home, GitMerge, BarChart3, Shield, ClipboardList, Link2, TrendingUp, Cpu } from "lucide-react";
import UserMenu from "./UserMenu";

const NAV = [
  { href: "/",           label: "홈",       Icon: Home },
  { href: "/dashboard",  label: "대시보드",  Icon: LayoutDashboard },
  { href: "/workflow",   label: "워크플로",  Icon: GitMerge },
  { href: "/studio",     label: "스튜디오",  Icon: Cpu },
  { href: "/report",     label: "리포트",    Icon: BarChart3 },
];

const GOV_NAV = [
  { href: "/governance", label: "거버넌스", Icon: ClipboardList },
  { href: "/security",   label: "보안",      Icon: Shield },
  { href: "/a2a",        label: "A2A",       Icon: Link2 },
  { href: "/roi",        label: "ROI",       Icon: TrendingUp },
];

export default function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-5xl px-6 py-3 flex items-center justify-between gap-4">
        {/* 로고 */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0">
          <Bot className="text-blue-600" size={26} />
          <div>
            <span className="text-lg font-bold text-gray-900 leading-none">AgentFlow</span>
            <p className="text-[10px] text-gray-400 leading-none mt-0.5">AI 에이전트 오케스트레이션</p>
          </div>
        </Link>

        {/* 내비게이션 */}
        <nav className="flex items-center gap-1">
          {NAV.map(({ href, label, Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/") && href !== "/";
            const isStudio = href === "/studio";
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  active && isStudio
                    ? "bg-violet-50 text-violet-700"
                    : active
                    ? "bg-blue-50 text-blue-700"
                    : isStudio
                    ? "text-violet-500 hover:text-violet-700 hover:bg-violet-50"
                    : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
                }`}
              >
                <Icon size={14} />
                {label}
              </Link>
            );
          })}

          <div className="w-px h-5 bg-gray-200 mx-1" />

          {GOV_NAV.map(({ href, label, Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? "bg-purple-50 text-purple-700"
                    : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
                }`}
              >
                <Icon size={14} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* 유저 메뉴 */}
        <UserMenu />
      </div>
    </header>
  );
}
