import React, { useState } from 'react'
import { supabase, saveRegistration, syncUserProfile, checkEmailExists } from './lib/supabase'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  reason?: string
  initialEmail?: string
  initialMode?: 'signin' | 'register'
  onSuccess?: () => void
}

export default function AuthModal({
  isOpen,
  onClose,
  reason,
  initialEmail = '',
  initialMode,
  onSuccess,
}: AuthModalProps) {
  const [mode, setMode] = useState<'signin' | 'register'>(initialMode || 'signin')
  const [email, setEmail] = useState(initialEmail)
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [company, setCompany] = useState('')

  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [infoMsg, setInfoMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Reset or initialize state whenever modal opens or initial props change
  React.useEffect(() => {
    if (isOpen) {
      setMode(initialMode || 'signin')
      setEmail(initialEmail || '')
      setPassword('')
      setFullName('')
      setCompany('')
      setErrorMsg(null)
      setInfoMsg(null)
      setSuccessMsg(null)
    }
  }, [isOpen, initialEmail, initialMode])

  if (!isOpen) return null

  // Check if user is already authenticated via Supabase Auth (e.g. Google OAuth)
  const isAlreadyAuthenticated = !!supabase.auth.getUser()

  const handleGoogleSignIn = async () => {
    setErrorMsg(null)
    setInfoMsg(null)
    setGoogleLoading(true)
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: window.location.origin,
        },
      })
      if (error) {
        setErrorMsg(error.message)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Google authentication failed')
    } finally {
      setGoogleLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)
    setInfoMsg(null)
    setSuccessMsg(null)
    setLoading(true)

    const cleanEmail = email.trim()

    try {
      if (mode === 'signin') {
        // 1. Check if this email exists in Supabase registrations or profiles
        const emailExists = await checkEmailExists(cleanEmail)

        if (!emailExists) {
          // First time user! Redirect to register tab
          setMode('register')
          setInfoMsg(`No account found for "${cleanEmail}". Please fill in your name and company below to complete registration.`)
          setLoading(false)
          return
        }

        // 2. Email exists -> attempt Sign In
        const { data, error } = await supabase.auth.signInWithPassword({
          email: cleanEmail,
          password,
        })

        if (error) {
          // If login failed because user was not found in Auth, redirect to register
          if (
            error.message.toLowerCase().includes('invalid login credentials') ||
            error.message.toLowerCase().includes('user not found')
          ) {
            setMode('register')
            setInfoMsg(`No account found for "${cleanEmail}". Please enter your full name and company to register.`)
          } else {
            setErrorMsg(error.message)
          }
        } else if (data.user) {
          await syncUserProfile(data.user)
          setSuccessMsg('Signed in successfully!')
          setTimeout(() => {
            onSuccess?.()
            onClose()
          }, 600)
        }
      } else {
        // Mode === 'register'
        if (!fullName.trim()) {
          setErrorMsg('Please enter your full name')
          setLoading(false)
          return
        }
        if (!company.trim()) {
          setErrorMsg('Please enter your company name')
          setLoading(false)
          return
        }

        // Save registration record
        await saveRegistration(cleanEmail, fullName.trim(), company.trim())

        // Check if user has an active session (e.g. from Google OAuth)
        const { data: sessionData } = await supabase.auth.getSession()
        const currentUser = sessionData?.session?.user

        if (currentUser) {
          // User already authenticated (Google OAuth) -> sync profile & finish registration
          await syncUserProfile(currentUser, {
            full_name: fullName.trim(),
            company: company.trim(),
          })

          setSuccessMsg('Registration completed successfully!')
          setTimeout(() => {
            onSuccess?.()
            onClose()
          }, 600)
        } else {
          // New email sign-up
          if (!password) {
            setErrorMsg('Please enter a password')
            setLoading(false)
            return
          }

          const { data, error } = await supabase.auth.signUp({
            email: cleanEmail,
            password,
            options: {
              data: {
                full_name: fullName.trim(),
                company: company.trim(),
              },
            },
          })

          if (error) {
            if (
              error.message.toLowerCase().includes('already registered') ||
              error.message.toLowerCase().includes('user_already_exists')
            ) {
              setMode('signin')
              setInfoMsg(`An account with "${cleanEmail}" already exists. Switched to Sign In mode.`)
            } else {
              setErrorMsg(error.message)
            }
          } else if (data.user) {
            await syncUserProfile(data.user, {
              full_name: fullName.trim(),
              company: company.trim(),
            })

            if (data.session) {
              setSuccessMsg('Account created successfully!')
              setTimeout(() => {
                onSuccess?.()
                onClose()
              }, 800)
            } else {
              setSuccessMsg('Registration successful! Check your email to confirm or sign in now.')
            }
          }
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }


  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(16, 42, 67, 0.75)',
        backdropFilter: 'blur(8px)',
        padding: 20,
      }}
      onClick={e => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 460,
          background: '#FFFFFF',
          borderRadius: 20,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(11, 104, 115, 0.1)',
          overflow: 'hidden',
          animation: 'fadeInUp 0.25s ease-out',
        }}
      >
        {/* Modal Header Banner */}
        <div
          style={{
            background: 'linear-gradient(135deg, #102A43 0%, #0B6873 100%)',
            padding: '28px 32px',
            color: 'white',
            position: 'relative',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              position: 'absolute',
              top: 16,
              right: 16,
              background: 'rgba(255, 255, 255, 0.15)',
              border: 'none',
              borderRadius: '50%',
              width: 32,
              height: 32,
              color: 'white',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
            }}
          >
            ✕
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: '#D66A2C',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path
                  d="M3 12L6 6L9 9L12 4"
                  stroke="white"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: '-0.02em' }}>DARA AI</span>
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 800, margin: '0 0 4px', color: 'white' }}>
            {mode === 'register' ? 'Create Your Account' : 'Welcome Back'}
          </h2>
          <p style={{ fontSize: 13, color: 'rgba(255, 255, 255, 0.75)', margin: 0 }}>
            {reason || 'Sign in or register to access AI Solder Paste Inspection features'}
          </p>
        </div>

        {/* Form Body */}
        <div style={{ padding: '28px 32px' }}>
          {/* Google Auth Button (Only in Sign In mode) */}
          {mode === 'signin' && (
            <>
              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={googleLoading}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  padding: '12px 20px',
                  borderRadius: 12,
                  border: '1px solid #E2E8F0',
                  background: '#FFFFFF',
                  color: '#1F2033',
                  fontWeight: 600,
                  fontSize: 14,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  boxShadow: '0 2px 4px rgba(0, 0, 0, 0.04)',
                  marginBottom: 20,
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = '#CBD5E1'
                  e.currentTarget.style.background = '#F8FAFC'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = '#E2E8F0'
                  e.currentTarget.style.background = '#FFFFFF'
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                {googleLoading ? 'Redirecting to Google...' : 'Continue with Google'}
              </button>

              {/* Divider */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                <div style={{ flex: 1, height: 1, background: '#E2E8F0' }} />
                <span style={{ fontSize: 11, fontWeight: 600, color: '#94A3B8', textTransform: 'uppercase' }}>
                  Or using email
                </span>
                <div style={{ flex: 1, height: 1, background: '#E2E8F0' }} />
              </div>
            </>
          )}

          {/* Tabs */}
          <div
            style={{
              display: 'flex',
              background: '#F1F5F9',
              borderRadius: 10,
              padding: 3,
              marginBottom: 20,
            }}
          >
            <button
              type="button"
              onClick={() => {
                setMode('register')
                setErrorMsg(null)
                setSuccessMsg(null)
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: 8,
                border: 'none',
                background: mode === 'register' ? '#FFFFFF' : 'transparent',
                color: mode === 'register' ? '#0B6873' : '#64748B',
                fontWeight: mode === 'register' ? 700 : 500,
                fontSize: 13,
                cursor: 'pointer',
                boxShadow: mode === 'register' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 0.2s',
              }}
            >
              Register
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('signin')
                setErrorMsg(null)
                setSuccessMsg(null)
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: 8,
                border: 'none',
                background: mode === 'signin' ? '#FFFFFF' : 'transparent',
                color: mode === 'signin' ? '#0B6873' : '#64748B',
                fontWeight: mode === 'signin' ? 700 : 500,
                fontSize: 13,
                cursor: 'pointer',
                boxShadow: mode === 'signin' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 0.2s',
              }}
            >
              Sign In
            </button>
          </div>

          {/* Info, Error & Success Messages */}
          {infoMsg && (
            <div
              style={{
                background: '#EFF6FF',
                border: '1px solid #93C5FD',
                color: '#1E40AF',
                borderRadius: 10,
                padding: '10px 14px',
                fontSize: 13,
                marginBottom: 16,
                lineHeight: 1.4,
              }}
            >
              {infoMsg}
            </div>
          )}

          {errorMsg && (
            <div
              style={{
                background: '#FEF2F2',
                border: '1px solid #FCA5A5',
                color: '#991B1B',
                borderRadius: 10,
                padding: '10px 14px',
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              {errorMsg}
            </div>
          )}

          {successMsg && (
            <div
              style={{
                background: '#ECFDF5',
                border: '1px solid #6EE7B7',
                color: '#065F46',
                borderRadius: 10,
                padding: '10px 14px',
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              {successMsg}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {mode === 'register' && (
              <>
                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#475569',
                      marginBottom: 4,
                    }}
                  >
                    Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Sarah Connor"
                    value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      borderRadius: 10,
                      border: '1px solid #CBD5E1',
                      fontSize: 14,
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>

                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#475569',
                      marginBottom: 4,
                    }}
                  >
                    Company / Organization *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Apex Electronics Mfg"
                    value={company}
                    onChange={e => setCompany(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      borderRadius: 10,
                      border: '1px solid #CBD5E1',
                      fontSize: 14,
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              </>
            )}

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  fontWeight: 600,
                  color: '#475569',
                  marginBottom: 4,
                }}
              >
                Work Email *
              </label>
              <input
                type="email"
                required
                placeholder="name@company.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: 10,
                  border: '1px solid #CBD5E1',
                  fontSize: 14,
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  fontWeight: 600,
                  color: '#475569',
                  marginBottom: 4,
                }}
              >
                Password *
              </label>
              <input
                type="password"
                required
                minLength={6}
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: 10,
                  border: '1px solid #CBD5E1',
                  fontSize: 14,
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: 6,
                background: '#D66A2C',
                color: 'white',
                border: 'none',
                borderRadius: 12,
                padding: '12px 24px',
                fontSize: 15,
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'background 0.2s',
                boxShadow: '0 4px 14px rgba(214, 106, 44, 0.35)',
              }}
              onMouseEnter={e => {
                if (!loading) e.currentTarget.style.background = '#B85320'
              }}
              onMouseLeave={e => {
                if (!loading) e.currentTarget.style.background = '#D66A2C'
              }}
            >
              {loading
                ? mode === 'register'
                  ? 'Registering...'
                  : 'Signing In...'
                : mode === 'register'
                ? 'Complete Registration'
                : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
