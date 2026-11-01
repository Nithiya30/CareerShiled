import React, { useState } from 'react';
import { Shield, Mail, Lock, UserPlus, ArrowRight } from 'lucide-react';
import api from '../services/api';

export default function AuthPage({ onAuthSuccess, serverError = '' }) {
  const [mode, setMode] = useState('signin');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const email = formData.email.trim();
      const password = formData.password;

      if (!email || !password) {
        setError('Email and password are required.');
        return;
      }

      let account;
      if (mode === 'signup') {
        const name = formData.name.trim();
        if (!name) {
          setError('Please enter your full name.');
          return;
        }
        if (password.length < 12) {
          setError('Password must be at least 12 characters long.');
          return;
        }
        if (formData.confirmPassword !== password) {
          setError('Passwords do not match.');
          return;
        }
        account = await api.register({
          name,
          email,
          password
        });
      } else {
        account = await api.login({ email, password });
      }

      onAuthSuccess(account);
    } catch (err) {
      setError(err.message || 'Authentication failed. Please try again.');
    } finally {
      setFormData((previous) => ({
        ...previous,
        password: '',
        confirmPassword: ''
      }));
      setLoading(false);
    }
  };

  const isSignIn = mode === 'signin';

  return (
    <div className="min-h-screen bg-shield-bg text-slate-100 flex items-center justify-center p-6">
      <div className="w-full max-w-md overflow-hidden rounded-2xl border border-shield-border bg-shield-surface shadow-2xl shadow-slate-950/30">
        <div className="p-8 md:p-10">
          <div className="flex justify-between items-center mb-8">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-cyan-400 font-mono">Access portal</p>
              <h2 className="mt-2 text-2xl font-bold text-slate-100">{isSignIn ? 'Welcome back' : 'Create account'}</h2>
            </div>
            <div className="rounded-full border border-shield-border bg-shield-card p-2 text-cyan-400">
              <Shield className="w-5 h-5" />
            </div>
          </div>

          <div className="mb-6 inline-flex rounded-lg border border-shield-border bg-shield-card p-1">
            <button
              type="button"
              onClick={() => setMode('signin')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                isSignIn ? 'bg-cyan-500 text-slate-950' : 'text-slate-300 hover:text-white'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setMode('signup')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                !isSignIn ? 'bg-cyan-500 text-slate-950' : 'text-slate-300 hover:text-white'
              }`}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isSignIn && (
              <div>
                <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">Full name</label>
                <div className="flex items-center gap-3 rounded-lg border border-shield-border bg-shield-card px-3 py-2.5">
                  <UserPlus className="w-4 h-4 text-slate-400" />
                  <input
                    name="name"
                    value={formData.name}
                    onChange={handleChange}
                    placeholder="Jane Doe"
                    className="w-full bg-transparent border-0 focus:outline-none text-sm text-slate-100 placeholder:text-slate-500"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">Email</label>
              <div className="flex items-center gap-3 rounded-lg border border-shield-border bg-shield-card px-3 py-2.5">
                <Mail className="w-4 h-4 text-slate-400" />
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="you@example.com"
                  className="w-full bg-transparent border-0 focus:outline-none text-sm text-slate-100 placeholder:text-slate-500"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">Password</label>
              <div className="flex items-center gap-3 rounded-lg border border-shield-border bg-shield-card px-3 py-2.5">
                <Lock className="w-4 h-4 text-slate-400" />
                <input
                  type="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder={isSignIn ? 'Enter your password' : 'Create a password'}
                  className="w-full bg-transparent border-0 focus:outline-none text-sm text-slate-100 placeholder:text-slate-500"
                />
              </div>
            </div>

            {!isSignIn && (
              <div>
                <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">Confirm password</label>
                <div className="flex items-center gap-3 rounded-lg border border-shield-border bg-shield-card px-3 py-2.5">
                  <Lock className="w-4 h-4 text-slate-400" />
                  <input
                    type="password"
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    placeholder="Re-enter password"
                    className="w-full bg-transparent border-0 focus:outline-none text-sm text-slate-100 placeholder:text-slate-500"
                  />
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">
                {error}
              </div>
            )}
            {serverError && !error && (
              <div className="rounded-lg border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
                {serverError}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? (
                <span>Processing...</span>
              ) : (
                <>
                  <span>{isSignIn ? 'Sign In' : 'Create Account'}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-xs text-slate-400">
            {isSignIn ? 'No account yet?' : 'Already registered?'}{' '}
            <button
              type="button"
              className="font-semibold text-cyan-400 underline-offset-4 hover:underline"
              onClick={() => setMode(isSignIn ? 'signup' : 'signin')}
            >
              {isSignIn ? 'Create one' : 'Sign in'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
