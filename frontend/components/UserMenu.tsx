"use client";

import { useSession, signOut } from "next-auth/react";
import { User, LogOut } from "lucide-react";

const ROLE_LABEL: Record<string, string> = {
  admin: "관리자",
  member: "멤버",
  viewer: "뷰어",
};

const ROLE_COLOR: Record<string, string> = {
  admin: "bg-red-100 text-red-700",
  member: "bg-blue-100 text-blue-700",
  viewer: "bg-gray-100 text-gray-600",
};

export default function UserMenu() {
  const { data: session } = useSession();
  if (!session?.user) return null;

  const role = session.user.role ?? "viewer";

  return (
    <div className="flex items-center gap-2">
      <div className="hidden sm:flex items-center gap-2">
        <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
          <User size={14} className="text-blue-600" />
        </div>
        <span className="text-sm text-gray-700 max-w-[120px] truncate">
          {session.user.name}
        </span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${ROLE_COLOR[role]}`}
        >
          {ROLE_LABEL[role]}
        </span>
      </div>
      <button
        onClick={() => signOut({ callbackUrl: "/login" })}
        className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
        title="로그아웃"
      >
        <LogOut size={15} />
      </button>
    </div>
  );
}
