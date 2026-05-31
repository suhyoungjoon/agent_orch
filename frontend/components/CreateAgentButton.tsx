"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { Plus } from "lucide-react";
import AgentFormModal from "./AgentFormModal";

export default function CreateAgentButton() {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);

  const canCreate =
    session?.user?.role === "admin" || session?.user?.role === "member";

  if (!canCreate) return null;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
      >
        <Plus size={14} />
        새 에이전트
      </button>

      {open && <AgentFormModal onClose={() => setOpen(false)} />}
    </>
  );
}
