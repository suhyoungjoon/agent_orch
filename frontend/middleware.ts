import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

export default withAuth(
  function middleware(req) {
    const isAuthPage =
      req.nextUrl.pathname === "/login" ||
      req.nextUrl.pathname === "/register";

    // 로그인된 사용자가 auth 페이지 접근 시 홈으로
    if (req.nextauth.token && isAuthPage) {
      return NextResponse.redirect(new URL("/", req.url));
    }
  },
  {
    callbacks: {
      authorized: ({ token, req }) => {
        const isAuthPage =
          req.nextUrl.pathname === "/login" ||
          req.nextUrl.pathname === "/register";
        return isAuthPage || !!token;
      },
    },
    pages: { signIn: "/login" },
  }
);

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
