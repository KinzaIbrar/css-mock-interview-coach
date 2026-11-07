import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import type { z } from 'zod'
import { toApiError } from '@/api/client'
import { PasswordField } from '@/components/auth/PasswordField'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Button } from '@/components/ui/Button'
import { TextInput } from '@/components/ui/Form'
import { Alert } from '@/components/ui/Feedback'
import { useAuth } from '@/context/AuthContext'
import { registerSchema } from '@/utils/schemas'

type Values = z.infer<typeof registerSchema>

export default function Register() {
  const { signUp } = useAuth()
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register, handleSubmit, setError, formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(registerSchema), defaultValues: { full_name: '', email: '', password: '', confirm: '' } })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      await signUp({ full_name: values.full_name.trim(), email: values.email.trim(), password: values.password })
      navigate('/dashboard', { replace: true })
    } catch (e) {
      const err = toApiError(e)
      if (err.status === 409) setError('email', { message: 'An account with this email already exists. Try signing in.' })
      else if (err.status === 422 && Object.keys(err.fieldErrors).length) {
        for (const [field, msg] of Object.entries(err.fieldErrors)) {
          if (field === 'email' || field === 'password' || field === 'full_name') setError(field, { message: msg })
        }
      } else setFormError(err.message)
    }
  })

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start practising in a minute. No payment details needed."
      footer={<>Already have an account? <Link to="/login" className="font-medium">Sign in</Link></>}
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError && <Alert tone="danger" live="alert">{formError}</Alert>}
        <TextInput label="Full name" autoComplete="name" error={errors.full_name?.message} {...register('full_name')} />
        <TextInput label="Email" type="email" autoComplete="email" inputMode="email" placeholder="you@example.com" error={errors.email?.message} {...register('email')} />
        <PasswordField label="Password" autoComplete="new-password" hint="At least 8 characters." error={errors.password?.message} {...register('password')} />
        <PasswordField label="Confirm password" autoComplete="new-password" error={errors.confirm?.message} {...register('confirm')} />
        <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>
          {isSubmitting ? 'Creating account' : 'Create account'}
        </Button>
      </form>
    </AuthLayout>
  )
}
