import { createClient, User } from '@supabase/supabase-js'

const SUPABASE_URL =
  import.meta.env.VITE_SUPABASE_URL || 'https://rkrddqnfszcgrlyxsmna.supabase.co'
const SUPABASE_ANON_KEY =
  import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_sDAUVytFmkVWg-K8-u_cCw_r_hF4cZ8'

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

export interface UserProfile {
  id: string
  email: string
  full_name?: string
  company?: string
  created_at?: string
}

export interface UserRegistration {
  id?: string
  email: string
  full_name: string
  company: string
  created_at?: string
}

/**
 * Retrieve saved registration record by email
 */
export async function getRegistrationDetails(email: string): Promise<UserRegistration | null> {
  const cleanEmail = email.trim()
  if (!cleanEmail) return null

  try {
    const { data: regData } = await supabase
      .from('registrations')
      .select('email, full_name, company')
      .ilike('email', cleanEmail)
      .maybeSingle()

    if (regData) {
      return regData as UserRegistration
    }

    const { data: profData } = await supabase
      .from('profiles')
      .select('email, full_name, company')
      .ilike('email', cleanEmail)
      .maybeSingle()

    if (profData && profData.full_name && profData.company) {
      return {
        email: profData.email,
        full_name: profData.full_name,
        company: profData.company,
      }
    }

    return null
  } catch (err) {
    return null
  }
}

/**
 * Ensures user record exists/updates in public.profiles table
 */
export async function syncUserProfile(
  user: User,
  extra?: { full_name?: string; company?: string }
): Promise<UserProfile | null> {
  if (!user || !user.id) return null

  const email = user.email || ''

  // Automatically retrieve registration details from public.registrations if not provided
  let regDetails: UserRegistration | null = null
  if (!extra?.full_name || !extra?.company) {
    regDetails = await getRegistrationDetails(email)
  }

  const full_name =
    extra?.full_name ||
    regDetails?.full_name ||
    user.user_metadata?.full_name ||
    user.user_metadata?.name ||
    email.split('@')[0] ||
    'User'
  const company =
    extra?.company ||
    regDetails?.company ||
    user.user_metadata?.company ||
    'Organization'

  try {
    const { data, error } = await supabase
      .from('profiles')
      .upsert(
        {
          id: user.id,
          email,
          full_name,
          company,
        },
        { onConflict: 'id' }
      )
      .select()
      .single()

    if (error) {
      console.warn('Profile sync warning:', error.message)
      return { id: user.id, email, full_name, company }
    }
    return data as UserProfile
  } catch (err) {
    console.error('Error syncing profile:', err)
    return { id: user.id, email, full_name, company }
  }
}

/**
 * Saves a new entry into public.registrations table
 */
export async function saveRegistration(
  email: string,
  fullName: string,
  company: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const { error } = await supabase.from('registrations').insert([
      {
        email,
        full_name: fullName,
        company,
      },
    ])

    if (error) {
      // Ignore unique violation if already registered
      if (error.code === '23505') {
        return { success: true }
      }
      return { success: false, error: error.message }
    }
    return { success: true }
  } catch (err: any) {
    return { success: false, error: err.message || 'Failed to save registration' }
  }
}

/**
 * Fetch existing profile for user
 */
export async function getUserProfile(userId: string): Promise<UserProfile | null> {
  try {
    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .maybeSingle()

    if (error || !data) return null
    return data as UserProfile
  } catch (err) {
    return null
  }
}

/**
 * Check if an email exists in public.registrations or public.profiles
 */
export async function checkEmailExists(email: string): Promise<boolean> {
  const cleanEmail = email.trim()
  if (!cleanEmail) return false

  try {
    // 1. Check registrations table
    const { data: regData } = await supabase
      .from('registrations')
      .select('email')
      .ilike('email', cleanEmail)
      .maybeSingle()

    if (regData) return true

    // 2. Check profiles table
    const { data: profData } = await supabase
      .from('profiles')
      .select('email')
      .ilike('email', cleanEmail)
      .maybeSingle()

    if (profData) return true

    return false
  } catch (err) {
    console.warn('Email check notice:', err)
    return false
  }
}

/**
 * Specifically check if an email is registered in public.registrations or public.profiles
 */
export async function isEmailRegistered(email: string): Promise<boolean> {
  return checkEmailExists(email)
}


