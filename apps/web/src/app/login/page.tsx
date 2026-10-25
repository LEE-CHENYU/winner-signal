import { Login } from "@/components/app";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; oauth_error?: string }>;
}) {
  const query = await searchParams;
  const next = query.next || "/dashboard";
  const safe = /^\/(dashboard(?:\/[a-f0-9]{32})?|submit)$/.test(next)
    ? next
    : "/dashboard";
  return <Login nextPath={safe} oauthError={!!query.oauth_error} />;
}
