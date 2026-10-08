-- Run after schema.sql. Enable pg_cron in Supabase Database > Extensions first.
-- Run as the SQL Editor's postgres role; never grant cron access to browsers.
select cron.schedule('credit-sure-retention', '0 2 * * *',
  'select public.purge_expired_research();');
-- Verify: select jobname, schedule, active from cron.job where jobname='credit-sure-retention';
