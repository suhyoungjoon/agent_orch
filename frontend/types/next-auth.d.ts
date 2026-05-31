import type { DefaultSession, DefaultUser } from "next-auth";
import type { DefaultJWT } from "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      role: "admin" | "member" | "viewer";
      teamId: string | null;
      accessToken: string;
    } & DefaultSession["user"];
  }

  interface User extends DefaultUser {
    role: "admin" | "member" | "viewer";
    teamId: string | null;
    accessToken: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT extends DefaultJWT {
    id: string;
    role: "admin" | "member" | "viewer";
    teamId: string | null;
    accessToken: string;
  }
}
