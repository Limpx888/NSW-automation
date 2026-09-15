import React, { useState } from 'react'
import type { User } from '@supabase/supabase-js'
import { supabase, type UserProfile } from './lib/supabase'

export default function ProfileView({
  onBack,
  user,
  profile,
}: {
  onBack: () => void
  user: User | null
  profile: UserProfile | null
}) {
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)
    setSuccessMsg(null)

    if (newPassword.length < 6) {
      setErrorMsg('Password must be at least 6 characters')
      return
    }

    if (newPassword !== confirmPassword) {
      setErrorMsg('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword })
      if (error) {
        setErrorMsg(error.message)
      } else {
        setSuccessMsg('Your password has been successfully updated.')
        setNewPassword('')
        setConfirmPassword('')
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'An unexpected error occurred while updating your password.')
    } finally {
      setLoading(false)
    }
  }

  const displayName =
    profile?.full_name ||
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email?.split('@')[0] ||
    'User'

  const company = profile?.company || 'No Company Provided'

  return (
    <div style={{ padding: '120px 48px', minHeight: '100vh', background: '#F7F6FB', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ width: '100%', maxWidth: 640 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 40 }}>
          <button
            type="button"
            onClick={onBack}
            style={{
              background: 'white',
              border: '1px solid #E2E8F0',
              borderRadius: '50%',
              width: 40,
              height: 40,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: '#475569',
              boxShadow: '0 2px 4px rgba(0,0,0,0.02)'
            }}
          >
            ←
          </button>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: '#1F2033', margin: 0 }}>My Profile</h1>
        </div>

        {/* Profile Card */}
        <div style={{ background: 'white', borderRadius: 16, padding: 32, boxShadow: '0 4px 12px rgba(0,0,0,0.04)', marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#1F2033', marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid #E2E8F0' }}>
            Account Information
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '16px 24px', fontSize: 14 }}>
            <div style={{ color: '#64748B', fontWeight: 600 }}>Name</div>
            <div style={{ color: '#1F2033', fontWeight: 500 }}>{displayName}</div>

            <div style={{ color: '#64748B', fontWeight: 600 }}>Email Address</div>
            <div style={{ color: '#1F2033', fontWeight: 500 }}>{user?.email}</div>

            <div style={{ color: '#64748B', fontWeight: 600 }}>Company</div>
            <div style={{ color: '#1F2033', fontWeight: 500 }}>{company}</div>
          </div>
        </div>

        {/* Password Update Card */}
        <div style={{ background: 'white', borderRadius: 16, padding: 32, boxShadow: '0 4px 12px rgba(0,0,0,0.04)' }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#1F2033', marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid #E2E8F0' }}>
            Change Password
          </h2>

          {errorMsg && (
            <div style={{ background: '#FEF2F2', border: '1px solid #FCA5A5', color: '#991B1B', borderRadius: 10, padding: '10px 14px', fontSize: 13, marginBottom: 20 }}>
              {errorMsg}
            </div>
          )}

          {successMsg && (
            <div style={{ background: '#ECFDF5', border: '1px solid #6EE7B7', color: '#065F46', borderRadius: 10, padding: '10px 14px', fontSize: 13, marginBottom: 20 }}>
              {successMsg}
            </div>
          )}

          <form onSubmit={handleUpdatePassword} style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 400 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                New Password
              </label>
              <input
                type="password"
                required
                minLength={6}
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                style={{
                  width: '100%', padding: '10px 14px', borderRadius: 10,
                  border: '1px solid #CBD5E1', fontSize: 14, outline: 'none', boxSizing: 'border-box'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                Confirm New Password
              </label>
              <input
                type="password"
                required
                minLength={6}
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                style={{
                  width: '100%', padding: '10px 14px', borderRadius: 10,
                  border: '1px solid #CBD5E1', fontSize: 14, outline: 'none', boxSizing: 'border-box'
                }}
              />
            </div>
            
            <button
              type="submit"
              disabled={loading || !newPassword || !confirmPassword}
              style={{
                marginTop: 8, background: '#0B6873', color: 'white', border: 'none',
                borderRadius: 10, padding: '12px 24px', fontSize: 14, fontWeight: 700,
                cursor: (loading || !newPassword || !confirmPassword) ? 'not-allowed' : 'pointer',
                opacity: (loading || !newPassword || !confirmPassword) ? 0.6 : 1,
                alignSelf: 'flex-start'
              }}
            >
              {loading ? 'Updating...' : 'Update Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
