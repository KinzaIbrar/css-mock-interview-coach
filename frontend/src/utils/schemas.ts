import { z } from 'zod'

// bcrypt (used by the backend) only accepts up to 72 BYTES, so count bytes, not characters.
const byteLength = (s: string) => new TextEncoder().encode(s).length

export const loginSchema = z.object({
  email: z.string().trim().min(1, 'Enter your email address').email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
})

export const registerSchema = z
  .object({
    full_name: z.string().trim().min(1, 'Enter your name').max(100, 'Use 100 characters or fewer'),
    email: z.string().trim().min(1, 'Enter your email address').email('Enter a valid email address'),
    password: z
      .string()
      .min(8, 'Use at least 8 characters')
      .refine((v) => byteLength(v) <= 72, 'Password is too long (72 bytes maximum)'),
    confirm: z.string().min(1, 'Re-enter your password'),
  })
  .refine((v) => v.password === v.confirm, { path: ['confirm'], message: 'Passwords do not match' })

export const setupSchema = z.object({
  subject: z.string().min(1, 'Choose a subject'),
  topic: z.string(),
  difficulty: z.enum(['mixed', 'easy', 'medium', 'hard']),
  num_questions: z.number({ error: 'Enter a number of questions' }).int('Use a whole number').min(1, 'Choose at least 1 question').max(20, 'Choose 20 questions or fewer'),
  duration_minutes: z.number({ error: 'Enter a duration' }).int('Use a whole number').min(5, 'Choose at least 5 minutes').max(120, 'Choose 120 minutes or fewer'),
  mode: z.enum(['mock', 'practice']),
})
