"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { Bot, Mail, Lock, User, Building2, Loader2 } from "lucide-react";
import Link from "next/link";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function RegisterPage() {
  const [form, setForm] = useState({
    teamName: "",
    name: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const update =
    (key: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${BASE_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          name: form.name,
          team_name: form.teamName,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail ?? "등록에 실패했습니다.");
        return;
      }

      const result = await signIn("credentials", {
        email: form.email,
        password: form.password,
        redirect: false,
      });

      if (result?.ok) {
        router.push("/");
        router.refresh();
      } else {
        router.push("/login");
      }
    } catch {
      setError("서버에 연결할 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-2">
            <Bot className="text-blue-600" size={28} />
            <span className="text-xl font-bold text-gray-900">AgentFlow</span>
          </div>
          <p className="text-sm text-gray-500">
            새 팀을 만들고 관리자 계정을 생성합니다
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field
              label="팀 이름"
              icon={<Building2 size={15} className="text-gray-400" />}
            >
              <input
                type="text"
                value={form.teamName}
                onChange={update("teamName")}
                placeholder="My Team"
                required
                className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </Field>

            <Field
              label="이름"
              icon={<User size={15} className="text-gray-400" />}
            >
              <input
                type="text"
                value={form.name}
                onChange={update("name")}
                placeholder="홍길동"
                required
                className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </Field>

            <Field
              label="이메일"
              icon={<Mail size={15} className="text-gray-400" />}
            >
              <input
                type="email"
                value={form.email}
                onChange={update("email")}
                placeholder="name@company.com"
                required
                className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </Field>

            <Field
              label="비밀번호"
              icon={<Lock size={15} className="text-gray-400" />}
              hint="최소 8자 이상"
            >
              <input
                type="password"
                value={form.password}
                onChange={update("password")}
                placeholder="••••••••"
                required
                minLength={8}
                className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </Field>

            {error && (
              <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  처리 중...
                </>
              ) : (
                "팀 만들기 & 시작"
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-sm text-gray-500 mt-4">
          이미 계정이 있으신가요?{" "}
          <Link
            href="/login"
            className="text-blue-600 hover:underline font-medium"
          >
            로그인
          </Link>
        </p>
      </div>
    </div>
  );
}

function Field({
  label,
  icon,
  hint,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2">{icon}</span>
        {children}
      </div>
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  );
}
