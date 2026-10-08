import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

const db = new PGlite();
const a = "00000000-0000-0000-0000-000000000001";
const b = "00000000-0000-0000-0000-000000000002";
const policy = "2026-10-08-research-v1";
const digest = "a".repeat(64);
const payload = { applicant_name: "Synthetic", age_years: 30 };
const result = { credit_score: 700, default_probability: 0.2, risk_band: "LOW", key_factors: [] };
await db.exec(`
  create role anon;
  create role authenticated;
  create role service_role bypassrls;
  create schema auth;
  create table auth.users(id uuid primary key);
  create function auth.uid() returns uuid language sql stable as $$
    select nullif(current_setting('request.jwt.claim.sub', true),'')::uuid;
  $$;
  grant usage on schema auth, public to anon, authenticated, service_role;
  insert into auth.users values ('${a}'),('${b}');
`);
const migration = await readFile(new URL("../supabase/schema.sql", import.meta.url), "utf8");
await db.exec(migration);
await db.exec(migration); // The migration must safely support reapplication.

async function asRole(role, fn) {
  await db.exec(`set role ${role}`);
  try { return await fn(); } finally { await db.exec("reset role"); }
}
async function save(owner, key, hash = digest, outcome = result) {
  return asRole("service_role", () => db.query(
    "select public.save_research_assessment($1,$2,$3,$4::jsonb,$5::jsonb,$6) as result",
    [owner, key, hash, JSON.stringify(payload), JSON.stringify(outcome), digest]));
}
let checks = 0;
async function check(name, fn) { await fn(); checks++; console.log(`PASS ${name}`); }

await check("schema readiness and direct write denial", async () => {
  const version = await asRole("service_role", () => db.query("select public.research_schema_version() as version"));
  assert.equal(version.rows[0].version, 2);
  for (const role of ["anon", "authenticated"]) {
    await assert.rejects(asRole(role, () => db.query("insert into public.credit_assessments(user_id,applicant_name,payload,result) values($1,'Forged','{}','{}')", [a])), /permission denied/);
    await assert.rejects(asRole(role, () => db.query("select public.accept_research_policy($1,$2)", [a,policy])), /permission denied/);
    await assert.rejects(asRole(role, () => db.query("select public.save_research_assessment($1,$2,$3,$4::jsonb,$5::jsonb,$6)", [a,crypto.randomUUID(),digest,JSON.stringify(payload),JSON.stringify(result),digest])), /permission denied/);
  }
});
await check("consent cannot be bypassed or modified", async () => {
  await assert.rejects(save(a, crypto.randomUUID()), /consent_required/);
  for (const owner of [a,b]) await asRole("service_role", () => db.query("select public.accept_research_policy($1,$2)", [owner,policy]));
  const first = await db.query("select accepted_at from public.account_consents where user_id=$1", [a]);
  await asRole("service_role", () => db.query("select public.accept_research_policy($1,$2)", [a,policy]));
  const second = await db.query("select accepted_at from public.account_consents where user_id=$1", [a]);
  assert.equal(first.rows[0].accepted_at.toISOString(), second.rows[0].accepted_at.toISOString());
  await assert.rejects(asRole("authenticated", () => db.query("update public.account_consents set accepted_at=now()")), /permission denied/);
});
const key = crypto.randomUUID();
await check("idempotent saves and changed-input conflict", async () => {
  const first = await save(a,key);
  const retry = await save(a,key,digest,{...result,credit_score:500});
  assert.deepEqual(first.rows[0].result,retry.rows[0].result);
  const count = await db.query("select count(*)::int as n from public.credit_assessments where user_id=$1",[a]);
  assert.equal(count.rows[0].n,1);
  await assert.rejects(save(a,key,"b".repeat(64)),/idempotency_conflict/);
});
await check("RLS hides the other account and anonymous reads fail", async () => {
  await save(b,crypto.randomUUID());
  await db.query("select set_config('request.jwt.claim.sub',$1,false)",[a]);
  const rows = await asRole("authenticated", () => db.query("select user_id from public.credit_assessments"));
  assert.equal(rows.rows.length,1); assert.equal(rows.rows[0].user_id,a);
  await assert.rejects(asRole("anon", () => db.query("select * from public.credit_assessments")),/permission denied/);
  await assert.rejects(asRole("authenticated", () => db.query("delete from public.credit_assessments")),/permission denied/);
});
await check("daily quota survives deletes and rejects excess writes", async () => {
  await db.query("update public.assessment_usage set count=100 where user_id=$1",[a]);
  await db.query("delete from public.credit_assessments where user_id=$1",[a]);
  await assert.rejects(save(a,crypto.randomUUID()),/quota_exceeded/);
});
await check("total record quota rejects excess writes", async () => {
  await db.query("insert into public.credit_assessments(user_id,applicant_name,payload,result) select $1,'Synthetic','{}','{}' from generate_series(1,499)",[b]);
  await assert.rejects(save(b,crypto.randomUUID()),/quota_exceeded/);
});
await check("retention hides expired records then removes them", async () => {
  await db.query("update public.credit_assessments set created_at=now()-interval '91 days' where user_id=$1",[b]);
  await db.query("select set_config('request.jwt.claim.sub',$1,false)",[b]);
  const visible = await asRole("authenticated", () => db.query("select * from public.credit_assessments"));
  assert.equal(visible.rows.length,0);
  await asRole("service_role", () => db.query("select public.purge_expired_research()"));
  const remaining = await db.query("select count(*)::int as n from public.credit_assessments where user_id=$1",[b]);
  assert.equal(remaining.rows[0].n,0);
});
await check("account deletion cascades to assessments, consent and counters", async () => {
  await db.query("delete from auth.users where id=$1",[b]);
  for (const table of ["credit_assessments","account_consents","assessment_usage"]) {
    const rows = await db.query(`select count(*)::int as n from public.${table} where user_id=$1`,[b]);
    assert.equal(rows.rows[0].n,0);
  }
});
await db.close();
console.log(`All ${checks} PostgreSQL policy/migration tests passed. Live Supabase and concurrent multi-instance checks remain required.`);
