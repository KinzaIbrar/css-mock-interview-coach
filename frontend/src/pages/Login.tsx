import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import type { z } from 'zod'
import { ApiError, toApiError } from '@/api/client'
import { PasswordField } from '@/components/auth/PasswordField'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Button } from '@/components/ui/Button'
import { TextInput } from '@/components/ui/Form'
import { Alert } from '@/components/ui/Feedback'
import { useAuth } from '@/context/AuthContext'
import { loginSchema } from '@/utils/schemas'

type Values = z.infer<typeof loginSchema>

export default function Login() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard'
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register, handleSubmit, setError, formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(loginSchema), defaultValues: { email: '', password: '' } })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      await signIn({ email: values.email, password: values.password })
      navigate(from, { replace: true })
    } catch (e) {
      const err: ApiError = toApiError(e)
      if (err.status === 401) setFormError('Incorrect email or password.')
      else if (err.status === 422) {
        for (const [field, msg] of Object.entries(err.fieldErrors)) if (field === 'email' || field === 'password') setError(field, { message: msg })
        if (!Object.keys(err.fieldErrors).length) setFormError(err.message)
      } else setFormError(err.message)
    }
  })

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue your interview practice."
      footer={<>New here? <Link to="/register" className="font-medium">Create an account</Link></>}
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError && <Alert tone="danger" live="alert">{formError}</Alert>}
        <TextInput label="Email" type="email" autoComplete="email" inputMode="email" placeholder="you@example.com" error={errors.email?.message} {...register('email')} />
        <PasswordField label="Password" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
        <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>
          {isSubmitting ? 'Signing in' : 'Sign in'}
        </Button>
      </form>
      <p className="mt-5 text-center text-xs text-muted">Forgot your password? Password reset is not available yet.</p>
    </AuthLayout>
  )
}
