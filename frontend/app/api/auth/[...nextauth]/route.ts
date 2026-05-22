import NextAuth, { type AuthOptions } from "next-auth";
import GitHubProvider from "next-auth/providers/github";

// Issue an HS256-signed JWT shaped like our backend expects:
//   { github_id, login, name, iat, exp }
// The shared secret comes from NEXTAUTH_SECRET; the backend uses the same env
// to verify.
const authOptions: AuthOptions = {
  providers: [
    GitHubProvider({
      clientId: process.env.GITHUB_OAUTH_ID ?? process.env.GITHUB_ID ?? "",
      clientSecret:
        process.env.GITHUB_OAUTH_SECRET ?? process.env.GITHUB_SECRET ?? "",
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, profile, account }) {
      // On first sign-in, store GitHub claims on the JWT.
      if (account && profile) {
        // GitHub profile has `id` (numeric) and `login`.
        // The TypeScript type is loose; cast to any to read provider fields.
          const gh = profile as any;
        token.github_id = gh.id ?? gh.sub;
        token.login = gh.login;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).github_id = token.github_id;
      (session as any).login = token.login;
      return session;
    },
  },
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
