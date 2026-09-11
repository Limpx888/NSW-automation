-- ================================================================
-- COMPLETE SUPABASE SQL SCRIPT FOR DARA AUTH & REGISTRATIONS
-- Copy and run this entire script in Supabase SQL Editor
-- ================================================================

-- 1. REGISTRATIONS TABLE
create table if not exists public.registrations (
  id uuid default gen_random_uuid() primary key,
  email text not null unique,
  full_name text not null,
  company text not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

alter table public.registrations enable row level security;

drop policy if exists "Anyone can register." on public.registrations;
drop policy if exists "Anyone can view registrations." on public.registrations;

create policy "Anyone can register."
  on public.registrations for insert
  with check ( true );

create policy "Anyone can view registrations."
  on public.registrations for select
  using ( true );


-- 2. PROFILES TABLE
create table if not exists public.profiles (
  id uuid references auth.users not null primary key,
  email text not null,
  full_name text,
  company text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

alter table public.profiles enable row level security;

drop policy if exists "Public profiles are viewable by everyone." on public.profiles;
drop policy if exists "Users can insert their own profile." on public.profiles;
drop policy if exists "Users can update own profile." on public.profiles;

create policy "Public profiles are viewable by everyone."
  on public.profiles for select
  using ( true );

create policy "Users can insert their own profile."
  on public.profiles for insert
  with check ( true );

create policy "Users can update own profile."
  on public.profiles for update
  using ( true );
